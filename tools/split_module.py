#!/usr/bin/env python3
"""Carve one module into siblings behind a facade, VERBATIM, and prove it.

The tool that applied the 2026-11-01 splits of `agents/common.py`,
`agents/composer.py` and `agents/perception.py` -- the fifth, sixth and seventh
facade splits; `docs/design/SPLIT_COMMON.md` records the method, and
`tools/module_anatomy.py` writes the report a plan is made from. It executes a
split plan the way this repository's own splits were executed
(docs/design/DESIGN_MODULE_LAYOUT.md, "Job 1: split behind facades";
docs/design/SPLIT_MEMORY.md is the worked example):

* lines 1..facade_keep_until_line (docstring + import block) stay in the
  facade byte-for-byte;
* every later top-level statement moves -- with the blank lines and comments
  above it -- to exactly one sibling `<pkg>/<stem>_<topic>.py`, unchanged;
* each sibling gets an import header computed from what its statements
  actually read: CPython's own scope analysis (`symtable`) for code, plus
  every annotation (which `symtable` does not see under `from __future__
  import annotations`), so neither of the two bugs SPLIT_MEMORY.md records
  for its extraction tool can recur (a function-local import marking a name
  bound module-wide; annotations and `returns` not visited);
* the facade re-exports every moved top-level binding explicitly, private
  names included, one per line, and defines nothing else.

THE PLAN is a JSON file:

    {"module": "agents/common.py",
     "facade_keep_until_line": 70,
     "siblings": [{"name": "common_base", "purpose": "...",
                   "symbols": ["_text", "LABEL_WORDS"]}, ...],
     "order": ["common_base", ...],
     "repoints": [{"file": "tests/test_x.py", "line": 12,
                   "kind": "setattr|getsource|__file__|path",
                   "name": "foo", "to": "agents.common_base"}]}

`module` is relative to `--root`. Lines 1..`facade_keep_until_line` are the
docstring and the module-level import block, which the facade keeps. Every
TOP-LEVEL name after them (def, class, constant) belongs to exactly one
sibling's `symbols`; a free comment block or marker attaches to the statement
after it, and `--list` prints the key a plan must use for a statement that
binds no name. A sibling is named `<stem>_<topic>` in the same package, the
sibling import graph must be a DAG (a cycle is broken by moving the shared
symbol DOWN into a leaf, never by merging), no sibling may import the facade,
and `order` is leaf-first. `repoints` lists the monkeypatch, source and path
pins the move makes inert, for the human applying it: the tool reports them
and edits no test.

CLI
  split_module.py --plan PLAN.json [--anatomy ANATOMY.json]
                  (--check | --apply | --list)
                  [--root DIR] [--python PY] [--force] [--date YYYY-MM-DD]
                  [--auto-attach] [--json-report OUT.json] [--no-info]
                  [--debug-drop-span KEY]

  --check   analyse, validate the generated text in memory, report; writes
            NOTHING (no import of the target either).
  --apply   as --check, then (only if there are no errors) snapshot the
            original module's namespace in a subprocess, write the siblings,
            rewrite the facade, and re-import both in a fresh subprocess to
            prove every former name resolves on the facade and `is` the
            object its sibling defines.
  --list    print every top-level statement after the header with the key a
            plan must use for it, then exit.

Exit status: 0 ok (warnings allowed) - 1 refused (errors) - 2 bad invocation
or malformed plan - 3 files written but verification failed (revert
instructions printed).

`--root` defaults to the checkout this file sits in, and `--python` to that
checkout's `.venv` interpreter (whichever of `bin/python` and
`Scripts/python.exe` exists), else the interpreter running this tool.
"""

from __future__ import annotations

import __future__ as _future
import argparse
import ast
import builtins
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import symtable
import tempfile
import textwrap
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

#: The checkout this file sits in: never a path written down here.
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
#: That checkout's own interpreter, which is what a split must import under.
DEFAULT_PYTHON = next(
    (candidate for candidate in (DEFAULT_ROOT / ".venv" / "bin" / "python",
                                 DEFAULT_ROOT / ".venv" / "Scripts" / "python.exe")
     if candidate.exists()),
    Path(sys.executable))
FACADE = "<facade>"
HEADER = "<header>"

BUILTIN_NAMES = frozenset(dir(builtins))
#: Names Python binds on every module without a statement doing it.
IMPLICIT_NAMES = frozenset({
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "__debug__", "__annotations__",
    "__cached__", "__path__",
})
MUTABLE_CTORS = {"dict", "list", "set", "defaultdict", "Counter", "Lock",
                 "RLock", "ContextVar", "deque", "OrderedDict", "Event",
                 "Semaphore", "BoundedSemaphore", "Queue",
                 "WeakKeyDictionary", "WeakValueDictionary", "WeakSet",
                 "LRUCache", "TTLCache"}
TRY_NODES = tuple(t for t in (ast.Try, getattr(ast, "TryStar", None)) if t)
TYPE_ALIAS = getattr(ast, "TypeAlias", None)
DEFINITION_KINDS = {"def", "async def", "class", "assign", "annassign", "type"}
SCOPE_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
MARK = "@@SPLIT_MODULE@@"


class PlanError(Exception):
    """The plan or the invocation is malformed (exit 2)."""


class VerbatimError(AssertionError):
    """The spans do not reproduce the original text: the move is not verbatim."""


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

class Diag:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def split_keepends(text: str) -> list[str]:
    """Lines split on '\\n' ONLY, ends kept.

    Not `str.splitlines`: that also splits on \\x0c, \\x1c-\\x1e, \\x85,
    \\u2028 and \\u2029, none of which ends a line for the Python tokenizer,
    so its line numbers would drift from the AST's on the first one.
    """
    parts = text.split("\n")
    out = [p + "\n" for p in parts[:-1]]
    if parts[-1]:
        out.append(parts[-1])
    return out


def normalize_tail(text: str) -> str:
    """Drop trailing whitespace-only lines; end with exactly one newline."""
    lines = split_keepends(text)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    out = "".join(lines)
    return out if out.endswith("\n") else out + "\n"


def leading_blank_lines(text: str) -> int:
    n = 0
    for line in split_keepends(text):
        if line.strip():
            break
        n += 1
    return n


def first_line(node) -> int:
    return min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", ())])


def snippet_of(lines, a, b, width=70) -> str:
    text = " ".join(l.strip() for l in lines[a - 1:min(b, a + 2)] if l.strip())
    return text if len(text) <= width else text[:width - 3] + "..."


def _target_names(t, out: list):
    if isinstance(t, ast.Name):
        out.append(t.id)
    elif isinstance(t, (ast.Tuple, ast.List)):
        for e in t.elts:
            _target_names(e, out)
    elif isinstance(t, ast.Starred):
        _target_names(t.value, out)


def _root_name(node):
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _mutated_bases(t, out: set):
    """Names whose OBJECT a target mutates (`X[k] = v`, `X.a = v`)."""
    if isinstance(t, (ast.Tuple, ast.List)):
        for e in t.elts:
            _mutated_bases(e, out)
    elif isinstance(t, ast.Starred):
        _mutated_bases(t.value, out)
    elif isinstance(t, (ast.Attribute, ast.Subscript)):
        root = _root_name(t)
        if root:
            out.add(root)


def _walrus_targets(expr, out: list):
    """NamedExpr targets an expression binds in the CURRENT scope."""
    if expr is None:
        return
    stack = [expr]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Lambda):
            continue
        if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
            out.append(n.target.id)
        stack.extend(ast.iter_child_nodes(n))


def _pattern_names(p, out: list):
    for n in ast.walk(p):
        if isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            out.append(n.name)
        elif isinstance(n, ast.MatchMapping) and n.rest:
            out.append(n.rest)


def is_type_checking_test(test) -> bool:
    return ((isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"))


def is_main_guard(node) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    t = node.test
    parts = [t.left] + list(t.comparators)
    names = [p for p in parts if isinstance(p, ast.Name) and p.id == "__name__"]
    consts = [p for p in parts if isinstance(p, ast.Constant) and p.value == "__main__"]
    return bool(names and consts)


def is_mutable_value(val) -> bool:
    if isinstance(val, (ast.List, ast.Dict, ast.Set, ast.ListComp,
                        ast.DictComp, ast.SetComp)):
        return True
    if isinstance(val, ast.Call):
        f = val.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        return name in MUTABLE_CTORS
    return False


# ---------------------------------------------------------------------------
# module-level bindings of one statement
# ---------------------------------------------------------------------------

@dataclass
class Bindings:
    binds: set = field(default_factory=set)        # unconditional
    cond: set = field(default_factory=set)         # only on some paths
    type_only: dict = field(default_factory=dict)  # name -> (if_node, import_node|None, alias|None)
    dels: set = field(default_factory=set)
    ann_only: set = field(default_factory=set)     # `X: T` with no value
    excepts: set = field(default_factory=set)      # `except E as e` (deleted after)
    imports: dict = field(default_factory=dict)    # name -> [(node, alias)] plain imports
    star: list = field(default_factory=list)
    mutated: set = field(default_factory=set)
    order: list = field(default_factory=list)      # ('bind'|'del', name) in source order

    def all_bound(self) -> set:
        return self.binds | self.cond | set(self.type_only) | self.ann_only | self.excepts


def module_bindings(node, b: Bindings | None = None, cond=False, tc_if=None) -> Bindings:
    """Names one top-level statement binds AT MODULE LEVEL.

    Hand-walked rather than read off `symtable`: CPython 3.12 inlines
    comprehensions (PEP 709) and its symtable then lists a module-level
    comprehension's iteration variable as an assigned MODULE name, which is
    false at runtime -- re-exporting it would be an ImportError.
    """
    b = b if b is not None else Bindings()

    def add(names, conditional=None):
        conditional = cond if conditional is None else conditional
        for n in names:
            if tc_if is not None:
                b.type_only.setdefault(n, (tc_if, None, None))
                continue
            (b.cond if conditional else b.binds).add(n)
            b.order.append(("bind", n))

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        add([node.name])
    elif TYPE_ALIAS is not None and isinstance(node, TYPE_ALIAS):
        add([node.name.id])
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for a in node.names:
            if a.name == "*":
                b.star.append(node)
                continue
            if isinstance(node, ast.ImportFrom):
                name = a.asname or a.name
            else:
                name = a.asname or a.name.split(".")[0]
            if tc_if is not None:
                b.type_only[name] = (tc_if, node, a)
                continue
            add([name])
            if not cond:
                b.imports.setdefault(name, []).append((node, a))
    elif isinstance(node, ast.Assign):
        out: list = []
        for t in node.targets:
            _target_names(t, out)
            _mutated_bases(t, b.mutated)
        _walrus_targets(node.value, out)
        add(out)
    elif isinstance(node, ast.AugAssign):
        out = []
        _target_names(node.target, out)
        _mutated_bases(node.target, b.mutated)
        _walrus_targets(node.value, out)
        add(out)
    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            if node.value is None:
                if tc_if is None:
                    b.ann_only.add(node.target.id)
            else:
                add([node.target.id])
        else:
            _mutated_bases(node.target, b.mutated)
        out = []
        _walrus_targets(node.value, out)
        add(out)
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        out = []
        _walrus_targets(node.iter, out)
        add(out)
        tgt: list = []
        _target_names(node.target, tgt)
        add(tgt, conditional=True)
        for s in node.body + node.orelse:
            module_bindings(s, b, True, tc_if)
    elif isinstance(node, ast.While):
        out = []
        _walrus_targets(node.test, out)
        add(out)
        for s in node.body + node.orelse:
            module_bindings(s, b, True, tc_if)
    elif isinstance(node, ast.If):
        if is_type_checking_test(node.test) and tc_if is None:
            for s in node.body:
                module_bindings(s, b, cond, node)
            for s in node.orelse:
                module_bindings(s, b, True, None)
        else:
            out = []
            _walrus_targets(node.test, out)
            add(out)
            branches = [node.body] + ([node.orelse] if node.orelse else [])
            _merge_branches(b, branches, cond, tc_if, exhaustive=bool(node.orelse))
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        out = []
        for item in node.items:
            _walrus_targets(item.context_expr, out)
            if item.optional_vars is not None:
                _target_names(item.optional_vars, out)
        add(out)
        for s in node.body:
            module_bindings(s, b, cond, tc_if)
    elif TRY_NODES and isinstance(node, TRY_NODES):
        # `try: import x / except ImportError: x = None` binds x on every path
        _merge_branches(b, [node.body] + [h.body for h in node.handlers], cond, tc_if,
                        exhaustive=bool(node.handlers))
        for h in node.handlers:
            if h.name:
                b.excepts.add(h.name)
        for s in node.orelse:
            module_bindings(s, b, True, tc_if)
        for s in node.finalbody:
            module_bindings(s, b, cond, tc_if)
    elif isinstance(node, ast.Match):
        out = []
        _walrus_targets(node.subject, out)
        add(out)
        for case in node.cases:
            caps: list = []
            _pattern_names(case.pattern, caps)
            _walrus_targets(case.guard, caps)
            add(caps, conditional=True)
            for s in case.body:
                module_bindings(s, b, True, tc_if)
    elif isinstance(node, ast.Delete):
        out = []
        for t in node.targets:
            _target_names(t, out)
            _mutated_bases(t, b.mutated)
        for n in out:
            b.dels.add(n)
            b.order.append(("del", n))
    else:
        out = []
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                _walrus_targets(child, out)
        add(out)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            root = _root_name(node.value.func) if isinstance(node.value.func, ast.Attribute) else None
            if root:
                b.mutated.add(root)
    return b


def _merge_branches(b: Bindings, branches: list, cond: bool, tc_if, exhaustive: bool):
    """Bind each branch separately; a name bound unconditionally in EVERY branch of an
    exhaustive choice (if/else, try/every-except) is unconditional, the rest conditional."""
    subs = []
    for body in branches:
        sb = Bindings()
        for s in body:
            module_bindings(s, sb, False, tc_if)
        subs.append(sb)
    always = set.intersection(*(sb.binds for sb in subs)) if (exhaustive and subs) else set()
    for sb in subs:
        for n in sb.binds | sb.cond:
            if n in always and not cond:
                b.binds.add(n)
            else:
                b.cond.add(n)
        for n, triple in sb.type_only.items():
            b.type_only.setdefault(n, triple)
        b.dels |= sb.dels
        b.ann_only |= sb.ann_only
        b.excepts |= sb.excepts
        b.star.extend(sb.star)
        b.mutated |= sb.mutated
        b.order.extend(sb.order)
        if not cond:
            for n, pairs in sb.imports.items():
                if n in always:
                    b.imports.setdefault(n, []).extend(pairs)


# ---------------------------------------------------------------------------
# what one statement READS from module globals
# ---------------------------------------------------------------------------

def symtable_refs(snippet: str, filename: str):
    """(global refs, class-local refs, global writes) of one top-level statement.

    Global refs: every name the statement loads at module level, and every
    name a nested function/lambda/comprehension resolves to the module
    (`is_global()`), which is exactly what the compiler turns into
    LOAD_GLOBAL. A function-local import or parameter therefore SHADOWS
    nothing beyond its own scope -- the first SPLIT_MEMORY bug cannot happen.

    Class-local refs: a class body reads with LOAD_NAME, which falls back to
    globals when the class-local is not bound YET; those are over-approximated
    as needed (safe direction) and reported.
    """
    top = symtable.symtable(snippet, filename, "exec")
    refs, class_local, writes = set(), set(), set()
    for s in top.get_symbols():
        if s.is_referenced():
            refs.add(s.get_name())
    stack = list(top.get_children())
    while stack:
        t = stack.pop()
        typ = str(t.get_type()).lower()
        for s in t.get_symbols():
            n = s.get_name()
            if s.is_declared_global() and s.is_assigned():
                writes.add(n)
            if not s.is_referenced():
                continue
            if s.is_global():
                refs.add(n)
            elif "class" in typ and not s.is_free():
                class_local.add(n)
        stack.extend(t.get_children())
    return refs, class_local, writes


def _string_annotation_names(value: str, out: set):
    try:
        sub = ast.parse(value.strip(), mode="eval")
    except SyntaxError:
        return
    _annotation_expr_names(sub.body, out, out)


def _annotation_expr_names(expr, names: set, str_names: set):
    """Names an annotation expression reads; strings parsed as forward refs.

    Strings inside `Literal[...]` are values, and Annotated's metadata is not
    a type, so neither is parsed.
    """
    stack = [expr]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            _string_annotation_names(n.value, str_names)
        elif isinstance(n, ast.Subscript):
            head = n.value
            hname = head.id if isinstance(head, ast.Name) else head.attr if isinstance(head, ast.Attribute) else ""
            stack.append(head)
            if hname == "Literal":
                continue
            if hname == "Annotated":
                sl = n.slice
                if isinstance(sl, ast.Tuple) and sl.elts:
                    stack.append(sl.elts[0])
                    for meta in sl.elts[1:]:
                        for m in ast.walk(meta):
                            if isinstance(m, ast.Name):
                                names.add(m.id)
                    continue
            stack.append(n.slice)
        else:
            stack.extend(ast.iter_child_nodes(n))


def annotation_names(stmt):
    """(names, names-from-string-annotations) of EVERY annotation in a statement.

    Under `from __future__ import annotations` symtable does not record
    annotation names at all, yet `typing.get_type_hints`, pydantic and
    FastAPI resolve them in the defining module's globals -- and without the
    future import they are evaluated when the `def` executes, at IMPORT (the
    second SPLIT_MEMORY bug: `-> Optional[Relationship]`).
    """
    names: set = set()
    str_names: set = set()
    for node in ast.walk(stmt):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    _annotation_expr_names(arg.annotation, names, str_names)
            if not isinstance(node, ast.Lambda) and node.returns is not None:
                _annotation_expr_names(node.returns, names, str_names)
        elif isinstance(node, ast.AnnAssign):
            _annotation_expr_names(node.annotation, names, str_names)
    return names, str_names - names


def module_level_dels_and_augs(stmt) -> set:
    """Names deleted or aug-assigned at MODULE level (symtable calls neither a read)."""
    out: list = []
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return set()
    stack = [stmt]
    while stack:
        n = stack.pop()
        if isinstance(n, SCOPE_DEFS):
            continue
        if isinstance(n, ast.Delete):
            for t in n.targets:
                _target_names(t, out)
        elif isinstance(n, ast.AugAssign):
            _target_names(n.target, out)
        stack.extend(ast.iter_child_nodes(n))
    return set(out)


def module_comprehension_only_names(stmt) -> set:
    """Iteration variables of module-level comprehensions that are read nowhere else.

    symtable (3.12, PEP 709) reports them as module-level references; they are
    comprehension-local at runtime.
    """
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return set()
    comp_targets: list = []
    inside: set = set()
    outside: set = set()

    def walk(n, in_comp):
        if isinstance(n, SCOPE_DEFS):
            return
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for g in n.generators:
                _target_names(g.target, comp_targets)
            for child in ast.iter_child_nodes(n):
                walk(child, True)
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            (inside if in_comp else outside).add(n.id)
        for child in ast.iter_child_nodes(n):
            walk(child, in_comp)

    walk(stmt, False)
    return set(comp_targets) - outside


def naive_names(stmt) -> set:
    """The over-approximating walk: every Name in Load/Del context, anywhere."""
    return {n.id for n in ast.walk(stmt)
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Load, ast.Del))}


def dynamic_namespace_uses(stmt) -> list:
    """Calls that read a module namespace dynamically: they now see the SIBLING's."""
    found = []
    for n in ast.walk(stmt):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id in ("globals", "vars", "eval", "exec") and (f.id != "vars" or not n.args):
                found.append(f"{f.id}() at line {n.lineno}")
        elif isinstance(n, ast.Subscript):
            v = n.value
            if (isinstance(v, ast.Attribute) and v.attr == "modules"
                    and isinstance(v.value, ast.Name) and v.value.id == "sys"
                    and isinstance(n.slice, ast.Name) and n.slice.id == "__name__"):
                found.append(f"sys.modules[__name__] at line {n.lineno}")
    return found


def getlogger_name_uses(stmt) -> list:
    out = []
    for n in ast.walk(stmt):
        if isinstance(n, ast.Call):
            f = n.func
            fname = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if fname == "getLogger" and any(isinstance(a, ast.Name) and a.id == "__name__" for a in n.args):
                out.append(n.lineno)
    return out


def bare_calls(stmt) -> set:
    return {n.func.id for n in ast.walk(stmt)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


# ---------------------------------------------------------------------------
# statements
# ---------------------------------------------------------------------------

def kind_of(node) -> str:
    table = {ast.FunctionDef: "def", ast.AsyncFunctionDef: "async def",
             ast.ClassDef: "class", ast.Assign: "assign",
             ast.AnnAssign: "annassign", ast.AugAssign: "augassign",
             ast.Import: "import", ast.ImportFrom: "import", ast.Expr: "expr",
             ast.If: "if", ast.For: "for", ast.AsyncFor: "async for",
             ast.While: "while", ast.With: "with", ast.AsyncWith: "async with",
             ast.Delete: "del", ast.Match: "match"}
    for k, v in table.items():
        if type(node) is k:
            return v
    if TRY_NODES and isinstance(node, TRY_NODES):
        return "try"
    if TYPE_ALIAS is not None and isinstance(node, TYPE_ALIAS):
        return "type"
    return type(node).__name__.lower()


def plan_names(node) -> list:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if TYPE_ALIAS is not None and isinstance(node, TYPE_ALIAS):
        return [node.name.id]
    if isinstance(node, ast.Assign):
        out: list = []
        for t in node.targets:
            _target_names(t, out)
        return list(dict.fromkeys(out))
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


@dataclass
class Stmt:
    i: int
    node: ast.stmt
    kind: str
    first: int
    last: int
    names: list
    key: str
    span: tuple = (0, 0)
    b: Bindings = None
    refs: set = field(default_factory=set)          # global refs (precise)
    class_local: set = field(default_factory=set)   # LOAD_NAME over-approx
    ann: set = field(default_factory=set)           # annotation names
    ann_str: set = field(default_factory=set)       # from string annotations
    naive: set = field(default_factory=set)
    writes: set = field(default_factory=set)        # `global X; X = ...`
    calls: set = field(default_factory=set)
    owner: str | None = None
    facade_reason: str | None = None
    auto: bool = False

    @property
    def label(self) -> str:
        what = " ".join(self.names) if self.names else self.key
        lines = f"L{self.first}" if self.first == self.last else f"L{self.first}-{self.last}"
        return f"{self.kind} {what} ({lines})"

    def needs(self) -> set:
        return self.refs | self.class_local | self.ann | self.ann_str


def analyse_statement(st: Stmt, lines, future_annotations: bool, filename: str):
    st.b = module_bindings(st.node)
    text = "".join(lines[st.first - 1:st.last])
    prefix = "from __future__ import annotations\n" if future_annotations else ""
    try:
        refs, class_local, writes = symtable_refs(prefix + text, filename)
    except SyntaxError as exc:  # pragma: no cover - the whole file parsed
        raise PlanError(f"cannot analyse {st.label}: {exc}")
    refs -= module_comprehension_only_names(st.node)
    refs |= module_level_dels_and_augs(st.node)
    st.refs, st.class_local, st.writes = refs, class_local - refs, writes
    st.ann, st.ann_str = annotation_names(st.node)
    st.naive = naive_names(st.node) | st.ann
    st.calls = bare_calls(st.node)


# ---------------------------------------------------------------------------
# header
# ---------------------------------------------------------------------------

@dataclass
class Header:
    n: int
    nodes: list = field(default_factory=list)
    kinds: dict = field(default_factory=dict)        # id(node) -> kind
    future: list = field(default_factory=list)       # future ImportFrom nodes
    imports: dict = field(default_factory=dict)      # name -> [(node, alias)]
    type_only: dict = field(default_factory=dict)    # name -> (if_node, node, alias)
    compound: dict = field(default_factory=dict)     # name -> node
    other: dict = field(default_factory=dict)        # name -> node
    star: list = field(default_factory=list)
    has_future_annotations: bool = False
    future_names: set = field(default_factory=set)   # `from __future__ import x` binds x
    replicas: dict = field(default_factory=dict)     # name -> (node, func source) for getLogger(__name__)
    also_kept: list = field(default_factory=list)    # body statements the plan keeps in the facade

    def runtime_names(self) -> set:
        return set(self.imports) | set(self.compound) | set(self.other) | self.future_names

    def all_names(self) -> set:
        return self.runtime_names() | set(self.type_only)


def logger_replica(node, src):
    """`X = <mod>.getLogger(__name__)`: (X, '<mod>.getLogger') -- else None.

    getLogger is a registry keyed by NAME, so a sibling that runs
    `X = logging.getLogger("<facade module>")` holds the very same Logger object:
    the one non-import header binding a sibling can reproduce without changing
    behaviour (and the logger keeps its name).
    """
    if not (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)):
        return None
    call = node.value
    f = call.func
    fname = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
    if fname != "getLogger" or call.keywords or len(call.args) != 1:
        return None
    if not (isinstance(call.args[0], ast.Name) and call.args[0].id == "__name__"):
        return None
    return node.targets[0].id, (ast.get_source_segment(src, f) or ast.unparse(f))


def read_header(tree, src, lines, n, diag: Diag) -> Header:
    h = Header(n=n)
    for idx, node in enumerate(tree.body):
        if first_line(node) > n:
            break
        if node.end_lineno > n:
            raise PlanError(
                f"facade_keep_until_line={n} cuts through the statement at lines "
                f"{first_line(node)}-{node.end_lineno} ({kind_of(node)}); move the "
                f"boundary to {first_line(node) - 1} or {node.end_lineno}")
        h.nodes.append(node)
        if idx == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            h.kinds[id(node)] = "docstring"
            continue
        register_header_node(h, node, src, lines, diag, f"header line {node.lineno}")
    return h


def register_header_node(h: Header, node, src, lines, diag: Diag, where: str):
    """Classify one statement the facade keeps: what a sibling may reproduce of it."""
    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
        h.kinds[id(node)] = "future"
        h.future.append(node)
        h.future_names.update(a.asname or a.name for a in node.names)
        if any(a.name == "annotations" for a in node.names):
            h.has_future_annotations = True
        return
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        h.kinds[id(node)] = "import"
        b = module_bindings(node)
        for name, pairs in b.imports.items():
            h.imports.setdefault(name, []).extend(pairs)
        h.star.extend(b.star)
        return
    b = module_bindings(node)
    if isinstance(node, ast.If) and is_type_checking_test(node.test) and not node.orelse \
            and all(isinstance(s, (ast.Import, ast.ImportFrom)) for s in node.body):
        h.kinds[id(node)] = "typecheck"
        h.type_only.update(b.type_only)
        return
    has_import = any(isinstance(s, (ast.Import, ast.ImportFrom)) for s in ast.walk(node))
    if isinstance(node, (ast.If, *TRY_NODES)) and has_import:
        h.kinds[id(node)] = "compound"
        for name in b.binds | b.cond:
            h.compound[name] = node
        h.type_only.update(b.type_only)
        h.star.extend(b.star)
        diag.warn(f"{where}: a {kind_of(node)} block binding "
                  f"{', '.join(sorted(b.binds | b.cond)) or 'nothing'}; a sibling that "
                  "needs one of its names gets the WHOLE block copied verbatim")
        return
    h.kinds[id(node)] = "other"
    for name in b.binds | b.cond:
        h.other[name] = node
    rep = logger_replica(node, src)
    if rep:
        h.replicas[rep[0]] = (node, rep[1])
        diag.info(f"{where}: `{snippet_of(lines, node.lineno, node.end_lineno)}` stays in the "
                  f"facade; a sibling that reads {rep[0]!r} gets `{rep[0]} = {rep[1]}(<module "
                  "name>)` -- the same Logger object, because getLogger is keyed by name")
        return
    diag.warn(f"{where}: a {kind_of(node)} statement that is not an "
              f"import ({snippet_of(lines, node.lineno, node.end_lineno)}); it stays in "
              "the facade, and no sibling may read what it binds")


# ---------------------------------------------------------------------------
# import formatting
# ---------------------------------------------------------------------------

def _alias_text(a) -> str:
    return a.name if not a.asname else f"{a.name} as {a.asname}"


def fmt_from(module: str, names: list, width=79) -> list:
    one = f"from {module} import {', '.join(names)}"
    if len(one) <= width:
        return [one]
    return [f"from {module} import ("] + [f"    {n}," for n in names] + [")"]


def fmt_import_node(node, aliases) -> list:
    if isinstance(node, ast.ImportFrom):
        mod = "." * node.level + (node.module or "")
        return fmt_from(mod, [_alias_text(a) for a in aliases])
    return [f"import {', '.join(_alias_text(a) for a in aliases)}"]


# ---------------------------------------------------------------------------
# project_check functions, executed from the repository's own source
# ---------------------------------------------------------------------------

PC_PURE = ("_calls_and_imports", "facade_import_violations", "_module_object_uses",
           "facade_siblings", "_module_level_bodies",
           # helpers the functions above and PC_DISK call, compiled with them
           "_may_name", "_import_nodes", "_facade_violations_in",
           "resolve_relative_import", "facade_dependencies",
           "facade_patch_sites", "_module_definitions")
PC_DISK = ("check_facade_import_direction", "check_facade_patch_targets")
PC_CONSTS = ("_MODULE_OBJECT_CALLS", "_MODULE_OBJECT_ATTRS", "_IMPLICIT_MODULE_NAMES",
             "_PER_MODULE_HOOKS", "_DUPLICATE_MIN_LINES")


def load_project_check(root: Path, diag: Diag) -> dict:
    """The repository's own check functions, compiled from tools/project_check.py.

    Read and exec'd, never imported: importing project_check imports the code
    map generator and the UI catalog extractor with it. Byte-identical to what
    `make structure` runs, so "the split passes them" is checked against the
    real thing rather than a paraphrase.
    """
    for candidate in (root / "tools" / "project_check.py",
                      DEFAULT_ROOT / "tools" / "project_check.py"):
        if candidate.is_file():
            break
    else:
        diag.warn("tools/project_check.py not found; its facade checks were not run")
        return {}
    try:
        tree = ast.parse(candidate.read_text(encoding="utf-8"))
        wanted = set(PC_PURE) | set(PC_DISK)
        picked = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                picked.append(node)
            elif isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in PC_CONSTS + ("FACADE_FAMILIES",)
                    for t in node.targets):
                picked.append(node)
        ns = {"ast": ast, "Path": Path, "defaultdict": defaultdict, "Counter": Counter,
              "__name__": "project_check_subset", "ROOT": root.resolve()}
        code = compile(ast.Module(body=picked, type_ignores=[]), str(candidate), "exec",
                       flags=_future.annotations.compiler_flag, dont_inherit=True)
        exec(code, ns)
        missing = [n for n in PC_PURE if n not in ns]
        if missing:
            diag.warn(f"project_check.py no longer defines {missing}; those checks were skipped")
        ns["__source__"] = str(candidate)
        return ns
    except Exception as exc:  # pragma: no cover - defensive
        diag.warn(f"could not load project_check functions ({exc!r}); facade checks skipped")
        return {}


# ---------------------------------------------------------------------------
# the split
# ---------------------------------------------------------------------------

@dataclass
class Split:
    plan: dict
    root: Path
    path: Path
    rel: str
    modname: str
    pkg: str
    pkg_dir: Path
    stem: str
    src: str
    lines: list
    tree: ast.Module
    header: Header
    stmts: list
    siblings: list                     # plan order
    sib_purpose: dict
    date: str
    diag: Diag
    order_topo: list = field(default_factory=list)
    module_bound: set = field(default_factory=set)
    binders: dict = field(default_factory=dict)       # name -> {owner}
    type_binders: dict = field(default_factory=dict)  # name -> {owner: (if, node, alias)}
    writers: dict = field(default_factory=dict)       # name -> {owner}
    final_ns: set = field(default_factory=set)
    last_owner: dict = field(default_factory=dict)
    exports: dict = field(default_factory=dict)       # sibling -> [names]
    defined: dict = field(default_factory=dict)       # sibling -> set
    needed: dict = field(default_factory=dict)        # sibling -> set
    header_used: dict = field(default_factory=dict)   # sibling -> [names]
    cross: dict = field(default_factory=dict)         # sibling -> {target: {name: [labels]}}
    guarded: dict = field(default_factory=dict)       # sibling -> [names]
    compound_used: dict = field(default_factory=dict) # sibling -> [nodes]
    import_lines: dict = field(default_factory=dict)  # sibling -> [lines]
    header_stmt_count: dict = field(default_factory=dict)
    texts: dict = field(default_factory=dict)         # sibling -> text
    body_texts: dict = field(default_factory=dict)
    facade_text: str = ""
    facade_kept: list = field(default_factory=list)
    imported_into: dict = field(default_factory=dict) # sibling -> set of names bound by imports
    unassigned_binds: set = field(default_factory=set)
    cyclic: bool = False
    replicas: dict = field(default_factory=dict)      # sibling -> [names replicated from getLogger]
    pc: dict = field(default_factory=dict)
    flagged: dict = field(default_factory=dict)       # sibling -> imported & called
    repoint_rows: list = field(default_factory=list)
    pin_rows: list = field(default_factory=list)
    contract: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)

    def sib_mod(self, sib: str) -> str:
        return f"{self.pkg}.{sib}" if self.pkg else sib

    def sib_path(self, sib: str) -> Path:
        return self.pkg_dir / f"{sib}.py"

    def owned(self, sib: str) -> list:
        return [s for s in self.stmts if s.owner == sib]


def load_plan(path: Path) -> dict:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError(f"cannot read plan {path}: {exc}")
    for key in ("module", "facade_keep_until_line", "siblings", "order"):
        if key not in plan:
            raise PlanError(f"plan {path} lacks {key!r}")
    if not isinstance(plan["siblings"], list) or not plan["siblings"]:
        raise PlanError("plan.siblings must be a non-empty list")
    for s in plan["siblings"]:
        if not isinstance(s, dict) or not {"name", "symbols"} <= set(s):
            raise PlanError(f"every sibling needs name and symbols: {s!r}"[:200])
        if not isinstance(s["symbols"], list):
            raise PlanError(f"sibling {s.get('name')}: symbols must be a list")
    return plan


def build_split(plan: dict, root: Path, date: str, diag: Diag) -> Split:
    rel = plan["module"]
    path = (root / rel).resolve()
    if not path.is_file():
        raise PlanError(f"module {rel} not found under {root}")
    if path.name == "__init__.py":
        raise PlanError("splitting a package __init__ is not supported")
    relp = path.relative_to(root.resolve())
    parts = list(relp.with_suffix("").parts)
    modname = ".".join(parts)
    pkg = ".".join(parts[:-1])
    stem = parts[-1]
    if not pkg:
        raise PlanError(f"{rel} is not inside a package; the facade-family rules "
                        "(tools/project_check.py) assume <pkg>/<stem>_*.py siblings")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PlanError(f"{rel} starts with a UTF-8 BOM; refusing (line slicing would shift)")
    src = raw.decode("utf-8")
    if re.search(r"\r(?!\n)", src):
        raise PlanError(f"{rel} contains a bare CR line ending; refusing")
    lines = split_keepends(src)
    tree = ast.parse(src, filename=str(path))
    n = plan["facade_keep_until_line"]
    if not isinstance(n, int) or n < 1 or n >= len(lines):
        raise PlanError(f"facade_keep_until_line={n!r} is outside 1..{len(lines) - 1}")
    header = read_header(tree, src, lines, n, diag)

    names = [s["name"] for s in plan["siblings"]]
    if len(set(names)) != len(names):
        raise PlanError(f"duplicate sibling names in plan: {sorted(k for k, v in Counter(names).items() if v > 1)}")
    for nm in names:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nm):
            raise PlanError(f"sibling name {nm!r} is not an identifier")
        if not nm.startswith(stem + "_"):
            raise PlanError(
                f"sibling {nm!r} does not start with {stem + '_'!r}: tools/project_check.py "
                "`facade_siblings` reads a family's members off the facade's import block by "
                "that prefix, so it would sit outside the facade rules")
    order = plan["order"]
    if sorted(order) != sorted(names):
        raise PlanError(f"plan.order {order} is not a permutation of the sibling names {names}")

    stmts = []
    body = [node for node in tree.body if first_line(node) > n]
    for i, node in enumerate(body):
        st = Stmt(i=i, node=node, kind=kind_of(node), first=first_line(node),
                  last=node.end_lineno, names=plan_names(node), key=f"@line:{node.lineno}")
        stmts.append(st)
    if not stmts:
        raise PlanError(f"nothing after line {n} to move")

    # spans: comments/blank lines attach to the statement that FOLLOWS them. A statement
    # that starts on the line where the previous one ends (`a = 1; b = 2`) has no lines of
    # its own: its text rides in the previous span (span None), and both must share an owner.
    prev_end = n
    head = None
    for st in stmts:
        if head is not None and st.first <= prev_end:
            st.span = None
            head.span = (head.span[0], max(head.span[1], st.last))
            prev_end = max(prev_end, st.last)
            continue
        st.span = (prev_end + 1, st.last)
        prev_end = st.last
        head = st
    head.span = (head.span[0], len(lines))

    filename = str(path)
    for st in stmts:
        analyse_statement(st, lines, header.has_future_annotations, filename)

    sp = Split(plan=plan, root=root, path=path, rel=relp.as_posix(), modname=modname,
               pkg=pkg, pkg_dir=path.parent, stem=stem, src=src, lines=lines, tree=tree,
               header=header, stmts=stmts, siblings=list(order),
               sib_purpose={s["name"]: str(s.get("purpose") or "").strip() for s in plan["siblings"]},
               date=date, diag=diag)
    return sp


# ---------------------------------------------------------------------------
# verbatim
# ---------------------------------------------------------------------------

def verify_verbatim(lines: list, header_n: int, spans: list) -> None:
    """Assert the spans, concatenated in order, ARE lines[header_n:] -- or raise.

    Checked structurally (contiguous, ordered, covering) and then literally
    (the joined text equals the original text), so a dropped, duplicated or
    reordered span fails loudly with the line numbers involved.
    """
    pos = header_n + 1
    for start, end in spans:
        if start != pos:
            if start > pos:
                raise VerbatimError(
                    f"VERBATIM CHECK FAILED: lines {pos}-{start - 1} belong to no span "
                    f"(dropped); the next span starts at {start}")
            raise VerbatimError(
                f"VERBATIM CHECK FAILED: span {start}-{end} overlaps or reorders "
                f"(expected a span starting at line {pos})")
        if end < start:
            raise VerbatimError(f"VERBATIM CHECK FAILED: empty or inverted span {start}-{end}")
        pos = end + 1
    if pos != len(lines) + 1:
        raise VerbatimError(
            f"VERBATIM CHECK FAILED: spans end at line {pos - 1} but the file has "
            f"{len(lines)} lines (lines {pos}-{len(lines)} dropped)")
    joined = "".join("".join(lines[s - 1:e]) for s, e in spans)
    if joined != "".join(lines[header_n:]):
        raise VerbatimError("VERBATIM CHECK FAILED: the concatenated spans differ from the original body text")


def span_text(sp: Split, st: Stmt) -> str:
    if st.span is None:
        return ""
    s, e = st.span
    return "".join(sp.lines[s - 1:e])


# ---------------------------------------------------------------------------
# ownership
# ---------------------------------------------------------------------------

def suggest_owner(sp: Split, st: Stmt) -> tuple:
    """(sibling, why) for an unassigned statement, or (None, '')."""
    votes = Counter()
    why = {}
    for n in sorted(st.b.all_bound() | st.b.dels | st.b.mutated):
        for o in sp.binders.get(n, ()):
            if o not in (FACADE, HEADER):
                votes[o] += 3
                why.setdefault(o, f"it binds/deletes/mutates {n}, which {o} owns")
    for n in sorted(st.refs):
        for o in sp.binders.get(n, ()):
            if o not in (FACADE, HEADER):
                votes[o] += 1
                why.setdefault(o, f"it reads {n}, which {o} owns")
    if votes:
        best = max(votes.items(), key=lambda kv: (kv[1], -sp.siblings.index(kv[0])))[0]
        return best, why[best]
    i = st.i
    for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(sp.stmts))):
        o = sp.stmts[j].owner
        if o and o != FACADE:
            return o, f"its neighbour {sp.stmts[j].label} lives there"
    return None, ""


def assign_owners(sp: Split, auto_attach: bool):
    diag = sp.diag
    name_to = {}
    for s in sp.plan["siblings"]:
        for sym in s["symbols"]:
            if not isinstance(sym, str):
                raise PlanError(f"sibling {s['name']}: symbol {sym!r} is not a string")
            if sym in name_to and name_to[sym] != s["name"]:
                diag.error(f"plan lists {sym!r} in two siblings: {name_to[sym]} and {s['name']}")
            name_to[sym] = s["name"]
    used = set()
    also = set(sp.plan.get("facade_also_keeps") or [])
    for sym in also:
        if sym in name_to:
            diag.error(f"{sym!r} is both in plan.facade_also_keeps and in sibling {name_to[sym]}")
    for st in sp.stmts:
        node = st.node
        if any(n == "__all__" for n in st.b.all_bound()) or (
                isinstance(node, ast.AugAssign) and _root_name(node.target) == "__all__") or (
                "__all__" in st.b.mutated):
            st.owner, st.facade_reason = FACADE, "__all__"
            used.update({st.key, *st.names} & set(name_to))
            diag.warn(f"{st.label} assigns __all__: kept in the FACADE (after the re-exports), "
                      "not moved; it now lists names the facade re-exports")
            continue
        if st.key in also or any(nm in also for nm in st.names):
            st.owner, st.facade_reason = FACADE, "also-kept"
            used.update({st.key, *st.names} & also)
            sp.header.also_kept.append(st.node)
            register_header_node(sp.header, node, sp.src, sp.lines, diag,
                                 f"facade_also_keeps {st.key}")
            diag.warn(f"{st.label} is KEPT IN THE FACADE (plan.facade_also_keeps), placed after the "
                      "re-exports in original order; siblings reproduce what they read of it the way "
                      "they reproduce the header")
            continue
        if is_main_guard(node):
            st.owner, st.facade_reason = FACADE, "__main__"
            used.update({st.key} & set(name_to))
            diag.warn(f"{st.label} is an `if __name__ == \"__main__\"` block: kept in the "
                      "FACADE (in a sibling it would never run under `python -m`)")
            continue
        owners = {}
        if st.key in name_to:
            owners[name_to[st.key]] = st.key
            used.add(st.key)
        for nm in st.names:
            if nm in name_to:
                owners.setdefault(name_to[nm], nm)
                used.add(nm)
        if st.key in name_to:
            explicit = name_to[st.key]
            others = {o for o in owners if o != explicit}
            if others:
                diag.error(f"{st.label}: {st.key} puts it in {explicit} but its name(s) put it in "
                           f"{sorted(others)}")
            st.owner = explicit
        elif len(owners) > 1:
            diag.error(f"{st.label} binds {st.names}, which the plan splits across "
                       f"{sorted(owners)}; one statement moves whole -- list its names in ONE sibling")
            st.owner = sorted(owners)[0]
        elif owners:
            st.owner = next(iter(owners))
    # binders from what is assigned so far (for suggestions)
    sp.binders = defaultdict(set)
    for st in sp.stmts:
        if st.owner:
            for n in st.b.all_bound():
                sp.binders[n].add(st.owner)
    unassigned = [st for st in sp.stmts if st.owner is None]
    for st in unassigned:
        sugg, why = suggest_owner(sp, st)
        if auto_attach and not st.names and sugg:
            st.owner, st.auto = sugg, True
            diag.warn(f"AUTO-ATTACHED {st.label} `{snippet_of(sp.lines, st.first, st.last)}` to "
                      f"{sugg} ({why}); write {st.key!r} into that sibling's symbols to make it explicit")
            for n in st.b.all_bound():
                sp.binders[n].add(sugg)
            continue
        hint = f"; suggest adding {(st.names[0] if st.names else st.key)!r} to {sugg} ({why})" if sugg else ""
        extra = ""
        if st.kind == "import" and st.first <= sp.header.n + 3:
            extra = (f" -- it directly follows the header: should facade_keep_until_line be "
                     f"{st.last}?")
        diag.error(f"UNASSIGNED top-level statement: line {st.first}, kind {st.kind}, "
                   f"{'name(s) ' + ', '.join(st.names) if st.names else 'key ' + st.key}: "
                   f"`{snippet_of(sp.lines, st.first, st.last)}`{hint}{extra}")
    if not used and sp.stmts and all(
            isinstance(st.node, ast.ImportFrom) and (st.node.module or "").rpartition(".")[2].startswith(sp.stem + "_")
            for st in sp.stmts):
        raise PlanError(f"{sp.rel} is already a facade (every statement after line {sp.header.n} "
                        f"re-exports from a {sp.stem}_* sibling); nothing to split")
    for sym in sorted(also - used):
        diag.error(f"plan.facade_also_keeps names {sym!r}, which is not a top-level statement after "
                   f"line {sp.header.n}")
    for sym in sorted(set(name_to) - used):
        where = ""
        if sym in sp.header.all_names():
            where = " (it is bound by the header, which the facade retains -- drop it from the plan)"
        elif sym.startswith("@line:"):
            where = " (no top-level statement after the header starts on that line)"
        diag.error(f"plan names {sym!r} (sibling {name_to[sym]}), which is not a top-level "
                   f"statement after line {sp.header.n}{where}")
    # statements sharing a line must move together
    for a, b in zip(sp.stmts, sp.stmts[1:]):
        if b.span is None and a.owner != b.owner:
            diag.error(f"{a.label} and {b.label} share line {b.first} but the plan separates them; "
                       "they move as one text, so list both in the same sibling")
    for sib in sp.siblings:
        if not sp.owned(sib):
            diag.error(f"sibling {sib} receives no statements")


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def analyse(sp: Split):
    diag = sp.diag
    h = sp.header
    sp.binders = defaultdict(set)
    sp.type_binders = defaultdict(dict)
    sp.writers = defaultdict(set)
    for st in sp.stmts:
        if st.owner is None or st.facade_reason == "also-kept":
            continue
        for n in st.b.binds | st.b.cond | st.b.ann_only | st.b.excepts:
            sp.binders[n].add(st.owner)
        for n, triple in st.b.type_only.items():
            sp.type_binders[n][st.owner] = triple
        for n in st.writes:
            sp.writers[n].add(st.owner)
        if st.b.star:
            diag.error(f"{st.label}: a star import after the header; its names are unknowable "
                       "statically, so neither the re-export nor any sibling header can be computed")
    if h.star:
        diag.warn("the header contains a star import; a sibling cannot reconstruct it, so any "
                  "name it supplies will be reported as unknown")
    sp.unassigned_binds = set()
    for st in sp.stmts:
        if st.owner is None:
            sp.unassigned_binds |= st.b.all_bound() | st.writes
    sp.module_bound = (h.all_names() | set(sp.binders) | set(sp.type_binders) | set(sp.writers)
                       | sp.unassigned_binds)

    for n, owners in sorted(sp.binders.items()):
        real = owners - {FACADE}
        if len(real) > 1:
            diag.error(f"{n!r} is bound at module level in {sorted(real)}; after the split each "
                       "sibling would hold its own binding. Put every statement binding it in ONE sibling")
        if n in h.runtime_names() and real:
            diag.warn(f"{n!r} is bound by the header AND redefined at module level in "
                      f"{sorted(real)}; siblings import it from there, and the facade's re-export "
                      "overrides the header binding exactly as the redefinition did")

    # final namespace and exports
    ns = set(h.runtime_names())
    last = {}
    for st in sp.stmts:
        if st.facade_reason == "also-kept":
            continue
        for kind, n in st.b.order:
            if kind == "bind":
                ns.add(n)
                last[n] = st.owner
            else:
                ns.discard(n)
                last.pop(n, None)
    sp.final_ns, sp.last_owner = ns, last
    sp.exports = {sib: [] for sib in sp.siblings}
    cond_all = set()
    for st in sp.stmts:
        cond_all |= st.b.cond
    for n in sorted(ns):
        o = last.get(n)
        if o in sp.exports:
            sp.exports[o].append(n)
            if n in cond_all and not any(n in st.b.binds for st in sp.stmts):
                diag.warn(f"{n!r} is only CONDITIONALLY bound (inside an if/for/try/match at module "
                          f"level, {o}); its re-export assumes the binding happened -- --apply "
                          "checks it against the real namespace")
            if n in ("__getattr__", "__dir__"):
                diag.warn(f"module-level {n} moves to {o}; the facade re-exports it, but it now "
                          "reads the SIBLING's globals")
    for sib in sp.siblings:
        sp.defined[sib] = set()
        for st in sp.owned(sib):
            sp.defined[sib] |= st.b.binds | st.b.cond | st.b.ann_only | st.b.excepts | set(st.b.type_only) | st.writes

    # per sibling classification
    for sib in sp.siblings:
        classify_sibling(sp, sib)

    check_global_rebinds(sp)
    note_shared_state(sp)
    note_moved_statements(sp)


def classify_sibling(sp: Split, sib: str):
    diag, h = sp.diag, sp.header
    stmts = sp.owned(sib)
    users = defaultdict(list)          # name -> [labels]
    for st in stmts:
        for n in st.needs():
            users[n].append(st.label)
    needed = {n for n in users if n in sp.module_bound}
    # unknown names: precise refs only (string annotations never count as unknown)
    for st in stmts:
        unknown = st.refs - sp.module_bound - BUILTIN_NAMES - IMPLICIT_NAMES
        if unknown:
            star = " (the header has a star import; it may come from there)" if h.star else ""
            diag.error(f"{sib}: {st.label} reads {sorted(unknown)}, which nothing at module level "
                       f"binds -- a latent NameError in the original too{star}")
        ann_unknown = st.ann - sp.module_bound - BUILTIN_NAMES - IMPLICIT_NAMES - st.refs
        if ann_unknown:
            diag.warn(f"{sib}: {st.label} annotates with {sorted(ann_unknown)}, which nothing at "
                      "module level binds (pre-existing; harmless only while annotations stay strings)")
    # dunders
    dunders = set()
    for st in stmts:
        dunders |= st.refs & IMPLICIT_NAMES
    if "__file__" in dunders:
        who = [st.label for st in stmts if "__file__" in st.refs]
        diag.warn(f"{sib}: __file__ is read by {who}; it now names {sib}.py, not {sp.stem}.py -- "
                  "a path computed from it resolves next to the SIBLING (same directory here; a "
                  "check of the file NAME or its contents changes)")
    if "__name__" in dunders:
        loggers = [f"{st.label}" for st in stmts if getlogger_name_uses(st.node)]
        if loggers:
            diag.warn(f"{sib}: logging.getLogger(__name__) in {loggers} now names the logger "
                      f"{sp.sib_mod(sib)!r} instead of {sp.modname!r}; handlers, levels or caplog "
                      f"filters keyed on {sp.modname!r} stop matching it")
        else:
            diag.info(f"{sib}: __name__ is read and now evaluates to {sp.sib_mod(sib)!r}")
    for d in sorted(dunders - {"__file__", "__name__"}):
        diag.info(f"{sib}: {d} is read and now describes {sib}.py")
    for st in stmts:
        dyn = dynamic_namespace_uses(st.node)
        if dyn:
            diag.warn(f"{sib}: {st.label} reads a namespace dynamically ({', '.join(dyn)}); it now "
                      f"sees {sp.sib_mod(sib)}'s globals, not the whole former module")

    header_names, guarded, compound, replicas = [], [], [], []
    cross = defaultdict(dict)
    pending = sorted(needed)
    seen = set()
    while pending:
        n = pending.pop(0)
        if n in seen:
            continue
        seen.add(n)
        if n in sp.defined[sib]:
            continue
        owners = (sp.binders.get(n, set()) | sp.writers.get(n, set())) - {sib}
        if not owners and n in sp.unassigned_binds and n not in h.all_names():
            continue  # bound only by an UNASSIGNED statement: that error already stands
        tb = sp.type_binders.get(n, {})
        if owners or tb:
            if FACADE in owners:
                diag.error(f"{sib}: {users[n]} read {n!r}, which stays in the facade "
                           f"({'/'.join(st.facade_reason for st in sp.stmts if st.owner == FACADE and n in st.b.all_bound()) or 'facade-kept'}); "
                           "a sibling may not import the facade")
                continue
            real = owners - {FACADE}
            if not real and tb:
                # type-only: guarded import reconstructed from the TYPE_CHECKING block
                (owner, triple), = list(tb.items())[:1]
                if triple[1] is None:
                    diag.error(f"{sib}: {users[n]} need the type-only name {n!r} bound under "
                               f"`if TYPE_CHECKING:` in {owner} by a non-import statement; it cannot "
                               "be reconstructed as a guarded import")
                    continue
                guarded.append((n, triple))
                for m in sorted(_test_names(triple[0])):
                    pending.append(m)
                    users[m].append(f"guarded import of {n}")
                continue
            if len(real) > 1:
                continue  # already an error
            target = next(iter(real))
            if n not in sp.final_ns or sp.last_owner.get(n) != target:
                if n in sp.writers and n not in sp.binders:
                    diag.error(f"{sib}: {users[n]} read {n!r}, which exists only once a function in "
                               f"{target} runs `global {n}; {n} = ...`; it cannot be imported -- move "
                               f"the readers into {target}")
                else:
                    diag.error(f"{sib}: {users[n]} read {n!r} from {target}, but {n!r} is not in "
                               f"{target}'s namespace once it has executed (deleted, an except-name "
                               "or annotation-only); move the readers into the same sibling")
                continue
            cross[target][n] = users[n]
            continue
        if n in h.imports:
            header_names.append(n)
            continue
        if n in h.type_only:
            guarded.append((n, h.type_only[n]))
            for m in sorted(_test_names(h.type_only[n][0])):
                pending.append(m)
                users[m].append(f"guarded import of {n}")
            continue
        if n in h.compound:
            node = h.compound[n]
            if node not in compound:
                compound.append(node)
                diag.warn(f"{sib}: {n!r} comes from the header {kind_of(node)} block at line "
                          f"{node.lineno}; the whole block is copied into {sib} verbatim")
                sub = symtable_refs("".join(sp.lines[first_line(node) - 1:node.end_lineno]),
                                    "<header>")[0]
                for m in sorted(sub & sp.module_bound):
                    pending.append(m)
                    users[m].append(f"header block at line {node.lineno}")
            continue
        if n in h.replicas:
            replicas.append(n)
            node, func = h.replicas[n]
            for m in sorted({x.id for x in ast.walk(node.value.func) if isinstance(x, ast.Name)}):
                pending.append(m)
                users[m].append(f"replica of {n}")
            continue
        if n in h.other:
            diag.error(f"{sib}: {users[n]} read {n!r}, bound in the header by a non-import "
                       f"statement (line {h.other[n].lineno}); a sibling cannot import it from the "
                       "facade -- end the header before it so it moves, or move it into a sibling")
            continue
    sp.needed[sib] = needed
    sp.header_used[sib] = sorted(set(header_names))
    sp.guarded[sib] = guarded
    sp.compound_used[sib] = compound
    sp.replicas[sib] = sorted(set(replicas))
    sp.cross[sib] = {t: dict(sorted(v.items())) for t, v in cross.items()}
    # shadowing info: the naive walk would have imported these
    naive = set()
    for st in stmts:
        naive |= st.naive
    shadowed = sorted((naive & sp.module_bound) - needed - sp.defined[sib] - IMPLICIT_NAMES)
    if shadowed:
        diag.info(f"{sib}: {len(shadowed)} module-level name(s) appear only as parameters/locals "
                  f"here and are NOT imported (the naive walk would have): {', '.join(shadowed[:12])}"
                  + (" ..." if len(shadowed) > 12 else ""))
    class_only = sorted(set().union(*[st.class_local for st in stmts]) & sp.module_bound - sp.defined[sib]) if stmts else []
    if class_only:
        diag.info(f"{sib}: class-body name(s) {class_only} are class-local but also module names; "
                  "imported anyway (a class body falls back to globals until the local is bound)")


def _test_names(if_node) -> set:
    return {n.id for n in ast.walk(if_node.test) if isinstance(n, ast.Name)}


def check_global_rebinds(sp: Split):
    diag = sp.diag
    for n, writer_owners in sorted(sp.writers.items()):
        w = writer_owners - {FACADE}
        writers = [st.label for st in sp.stmts if n in st.writes]
        if len(w) > 1:
            diag.error(f"`global {n}` is rebound by functions in {sorted(w)} ({writers}); each "
                       "would rebind its OWN module's name and the others would never see it")
            continue
        if not w:
            continue
        W = next(iter(w))
        definers = sp.binders.get(n, set()) - {FACADE}
        if definers and definers != {W}:
            diag.error(f"`global {n}` is rebound in {W} ({writers}) but {n!r} is defined in "
                       f"{sorted(definers)}: the rebind would land in {W}'s globals and every reader "
                       f"in {sorted(definers)} keeps the initial value forever. Keep them together")
        if n in sp.header.runtime_names() and not definers:
            diag.warn(f"`global {n}` rebinds a HEADER-bound name in {W} ({writers}); after the "
                      f"split the facade's {n} and every other sibling's copy keep the original")
        for sib in sp.siblings:
            if sib == W:
                continue
            if n in sp.needed.get(sib, ()):
                readers = [st.label for st in sp.owned(sib) if n in st.needs()]
                diag.error(f"{sib} reads {n!r} ({readers}) but `global {n}` rebinds it in {W} "
                           f"({writers}); {sib} imported the value once and never sees a rebind. "
                           f"Move the readers into {W}")
        if n in sp.exports.get(W, ()):
            diag.warn(f"{n!r} is rebound by `global` in {W} ({writers}); the facade's re-export is "
                      f"a SNAPSHOT of the initial value, so `{sp.stem}.{n}` no longer tracks the "
                      f"rebind (read it as `{sp.sib_mod(W)}.{n}`)")
        elif n not in sp.final_ns:
            diag.warn(f"{n!r} exists only after a function in {W} runs `global {n}` "
                      f"({writers}); `{sp.stem}.{n}` will never appear on the facade")


def note_shared_state(sp: Split):
    diag = sp.diag
    for st in sp.stmts:
        if st.owner in (None, FACADE):
            continue
        node = st.node
        val = getattr(node, "value", None)
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or val is None or not is_mutable_value(val):
            continue
        for n in st.names:
            others = [sib for sib in sp.siblings if sib != st.owner and n in sp.needed.get(sib, ())]
            if others:
                diag.info(f"shared mutable {n!r} ({st.owner}) is read/mutated by {others}: one object, "
                          "so mutation is shared -- a rebind would not be")


def note_moved_statements(sp: Split):
    diag = sp.diag
    moved_defs = 0
    for st in sp.stmts:
        if st.owner in (None, FACADE):
            continue
        if st.kind in ("def", "async def", "class"):
            moved_defs += 1
        if st.kind in DEFINITION_KINDS:
            continue
        snip = snippet_of(sp.lines, st.first, st.last)
        if st.kind == "expr" and isinstance(st.node.value, ast.Constant):
            diag.info(f"{st.label} is a bare constant expression; it moves to {st.owner}")
            continue
        diag.warn(f"import-time side effect moves to sibling {st.owner}; import order changes: "
                  f"{st.label} `{snip}`")
        if st.kind == "if" and is_type_checking_test(st.node.test):
            diag.info(f"{st.label} is a TYPE_CHECKING block; its names are type-only: not "
                      "re-exported, and other siblings that annotate with them get a guarded import")
    coords = Counter()
    for st in sp.stmts:
        if st.owner in (None, FACADE):
            continue
        for n in ast.walk(st.node):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and (
                    n.value == sp.modname or n.value.startswith(sp.modname + ".")):
                coords[st.owner] += 1
    if coords:
        diag.info(f"{sum(coords.values())} string literal(s) spell {sp.modname!r} "
                  f"({', '.join(f'{k} {v}' for k, v in sorted(coords.items()))}); they move "
                  "verbatim. A dotted name inside a string is a namespace coordinate (a language-pack "
                  "key, a hash seed), not an import: do NOT rewrite them to the sibling")
    if moved_defs:
        diag.info(f"{moved_defs} functions/classes now report their sibling as __module__ (e.g. "
                  f"{sp.sib_mod(sp.siblings[0])!r}, was {sp.modname!r}): repr, pickle-by-reference of "
                  "new objects and __module__-keyed registries see the change; __qualname__ does not")


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

def sibling_edges(sp: Split) -> dict:
    return {sib: set(sp.cross.get(sib, {})) for sib in sp.siblings}


def find_sccs(nodes, edges) -> list:
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in sorted(edges.get(v, ())):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(comp)

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    for v in nodes:
        if v not in index:
            strong(v)
    return out


def one_cycle(comp, edges) -> list:
    comp = set(comp)
    start = sorted(comp)[0]
    path, seen = [start], {start}

    def dfs(v):
        for w in sorted(edges.get(v, ())):
            if w not in comp:
                continue
            if w == start:
                return True
            if w not in seen:
                seen.add(w)
                path.append(w)
                if dfs(w):
                    return True
                path.pop()
        return False

    dfs(start)
    return path + [start]


def breaks_edge(sp: Split, a: str, b: str, names: set) -> bool:
    """Would moving the statements that define `names` from b into a remove the a -> b edge?"""
    defs = [st for st in sp.owned(b) if st.b.all_bound() & names]
    moved = set().union(*(st.b.all_bound() for st in defs)) if defs else set()
    if names - moved:
        return False
    for st in sp.owned(b):
        if st not in defs and st.needs() & moved:
            return False            # something left behind still reads them
    for st in defs:
        if (st.needs() & sp.defined[b]) - moved:
            return False            # they read their old home: the edge would survive
    others = set(sp.cross[a][b]) - names
    return not others


PURE_DECORATORS = frozenset({
    "property", "staticmethod", "classmethod", "dataclass", "lru_cache", "cache",
    "cached_property", "wraps", "contextmanager", "asynccontextmanager", "overload",
    "abstractmethod", "total_ordering", "final", "runtime_checkable", "singledispatch",
    "singledispatchmethod", "override", "validator", "field_validator", "root_validator",
    "model_validator", "computed_field", "unique",
})


def registering_decorators(node) -> list:
    """Decorators that may register the definition somewhere (anything not known-pure)."""
    out = []
    for d in getattr(node, "decorator_list", ()):
        target = d.func if isinstance(d, ast.Call) else d
        last = target.attr if isinstance(target, ast.Attribute) else target.id if isinstance(target, ast.Name) else ""
        if last in PURE_DECORATORS:
            continue
        root = _root_name(target)
        if root:
            out.append(ast.unparse(target))
    return out


def execution_order(sp: Split) -> list:
    """The order the siblings' bodies actually RUN: the facade imports them in plan order,
    and each sibling first imports the siblings it needs (in plan order)."""
    done, order = set(), []

    def visit(s, stack=()):
        if s in done or s in stack:
            return
        for t in sp.siblings:
            if t in sp.cross.get(s, {}):
                visit(t, stack + (s,))
        done.add(s)
        order.append(s)

    for s in sp.siblings:
        visit(s)
    return order


def check_effect_order(sp: Split):
    """Import-time effects (module-level statements, registering decorators) must keep
    their relative order -- FastAPI matches routes first-registered-first, middleware
    wraps in the order it is added, a registry built by a loop is read in insertion order."""
    diag = sp.diag
    if sp.cyclic:
        return  # no execution order exists until the cycle is broken
    effectful = {}
    for st in sp.stmts:
        if st.owner in (None, FACADE):
            continue
        decos = registering_decorators(st.node)
        if st.kind not in DEFINITION_KINDS and not (st.kind == "expr" and isinstance(st.node.value, ast.Constant)):
            effectful[st.i] = st.kind
        elif decos:
            effectful[st.i] = "@" + decos[0]
    if not effectful:
        return
    exec_order = execution_order(sp)
    rank = {s: k for k, s in enumerate(exec_order)}
    new = sorted(effectful, key=lambda i: (rank[sp.stmts[i].owner], i))
    old = sorted(effectful)
    if new == old:
        diag.info(f"{len(old)} import-time effect(s) (module-level statements and registering "
                  f"decorators) keep their relative order: siblings run as {' -> '.join(exec_order)}")
        return
    pos = {i: k for k, i in enumerate(new)}
    by_kind = Counter()
    examples = []
    for a_idx, a in enumerate(old):
        for b in old[a_idx + 1:]:
            if pos[a] > pos[b]:
                key = effectful[a] if effectful[a] == effectful[b] else f"{effectful[a]} / {effectful[b]}"
                by_kind[key] += 1
                if len(examples) < 4:
                    examples.append(f"{sp.stmts[a].label} [{sp.stmts[a].owner}] now runs after "
                                    f"{sp.stmts[b].label} [{sp.stmts[b].owner}]")
    kinds = ", ".join(f"{k}: {v}" for k, v in by_kind.most_common(6))
    diag.warn(f"IMPORT-TIME EFFECT ORDER CHANGES ({sum(by_kind.values())} inverted pair(s); siblings "
              f"run as {' -> '.join(exec_order)}). By kind: {kinds}. E.g. " + "; ".join(examples)
              + ". Route/middleware/registry order may matter: keep effectful statements in "
              "file order across siblings, or confirm the order is irrelevant")


def check_dag(sp: Split):
    diag = sp.diag
    edges = sibling_edges(sp)
    cyclic = False
    for comp in find_sccs(sp.siblings, edges):
        if len(comp) < 2:
            continue
        cyclic = True
        cyc = one_cycle(comp, edges)
        parts = []
        free_edges = []
        for a, b in zip(cyc, cyc[1:]):
            names = sp.cross[a][b]
            detail = []
            all_free = True
            for n, u in list(names.items()):
                home = [st.label for st in sp.owned(b) if n in st.needs() and n not in st.names]
                all_free = all_free and not home
                if len(detail) < 6:
                    detail.append(f"{n} (read by {', '.join(sorted(set(u))[:3])}"
                                  f"{', ...' if len(set(u)) > 3 else ''}; "
                                  + (f"also read in {b} by {', '.join(home[:2])}" if home
                                     else f"nothing in {b} reads it") + ")")
            if all_free and breaks_edge(sp, a, b, set(names)):
                free_edges.append((a, b, sorted(names)))
            more = f" [+{len(names) - 6} more]" if len(names) > 6 else ""
            parts.append(f"\n      {a} -> {b} via {len(names)} name(s): {'; '.join(detail)}{more}")
        if free_edges:
            a, b, names = min(free_edges, key=lambda e: len(e[2]))
            fix = (f"\n      cheapest fix: move {names} from {b} into {a} -- nothing else in {b} reads "
                   f"them and they read nothing else from {b}, so the {a} -> {b} edge disappears")
        else:
            fix = (f"\n      no edge can be dropped by moving its names into the importer (each is read "
                   f"at home, or reads its home): move the smallest set DOWN into a leaf both import "
                   f"(e.g. {sp.stem}_common)")
        diag.error(f"IMPORT CYCLE among siblings {' -> '.join(cyc)} (component {sorted(comp)}):"
                   + "".join(parts) + fix + "; never merge the siblings")
    # topological order, leaf first, ties broken by plan order
    remaining = {s: set(edges[s]) for s in sp.siblings}
    order = []
    while remaining:
        ready = [s for s in sp.siblings if s in remaining and not (remaining[s] - set(order))]
        if not ready:
            order.extend(s for s in sp.siblings if s in remaining)
            break
        order.append(ready[0])
        del remaining[ready[0]]
    sp.order_topo = order
    sp.cyclic = cyclic
    if cyclic:
        return
    pos = {s: i for i, s in enumerate(sp.siblings)}
    for a in sp.siblings:
        for b in edges[a]:
            if pos[b] > pos[a]:
                diag.warn(f"plan.order lists {a} before {b}, which it imports; leaf-first would put "
                          f"{b} first (suggested order: {', '.join(order)})")


# ---------------------------------------------------------------------------
# text generation
# ---------------------------------------------------------------------------

def sibling_docstring(sp: Split, sib: str) -> str:
    purpose = sp.sib_purpose.get(sib) or f"Part of {sp.rel}, carved out by split_module.py."
    purpose = purpose.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    first = textwrap.fill(purpose, width=76, break_on_hyphens=False)
    second = textwrap.fill(
        f"Carved verbatim from `{sp.rel}` on {sp.date}; `{sp.rel}` is now a facade that "
        "re-exports every name defined here (docs/design/DESIGN_MODULE_LAYOUT.md).", width=76,
        break_on_hyphens=False)
    return f'"""{first}\n\n{second}\n"""\n'


def build_import_header(sp: Split, sib: str) -> list:
    """Lines of the sibling's import block, and the count of statements in it."""
    h = sp.header
    out = []
    count = 0
    for node in h.future:
        out.extend(fmt_import_node(node, node.names))
        count += 1
    if h.future:
        out.append("")
    want = set(sp.header_used[sib])
    body_lines = []
    for node in h.nodes + h.also_kept:
        kind = h.kinds.get(id(node))
        if kind == "import":
            chosen = [a for a in node.names if a.name != "*" and
                      (a.asname or (a.name if isinstance(node, ast.ImportFrom) else a.name.split(".")[0])) in want]
            if chosen:
                body_lines.extend(fmt_import_node(node, chosen))
                count += 1
        elif kind == "compound" and node in sp.compound_used[sib]:
            body_lines.extend(l.rstrip("\n") for l in sp.lines[first_line(node) - 1:node.end_lineno])
            count += 1
    out.extend(body_lines)
    for n in sp.replicas.get(sib, ()):
        node, func = h.replicas[n]
        out.append(f"{n} = {func}({json.dumps(sp.modname)})")
        count += 1
    # guarded TYPE_CHECKING imports, grouped by their if-test text
    groups = {}
    for n, (if_node, imp, alias) in sp.guarded[sib]:
        test = ast.get_source_segment(sp.src, if_node.test) or ast.unparse(if_node.test)
        g = groups.setdefault(test, {})
        g.setdefault(id(imp), (imp, []))[1].append(alias)
    for test, imps in groups.items():
        if out and out[-1] != "":
            out.append("")
        out.append(f"if {test}:")
        for imp, aliases in imps.values():
            keep = [a for a in imp.names if any(a is x for x in aliases)]
            out.extend("    " + l for l in fmt_import_node(imp, keep))
        count += 1
    sibs = [t for t in sp.siblings if t in sp.cross[sib]]
    if sibs:
        if out and out[-1] != "":
            out.append("")
        for t in sibs:
            out.extend(fmt_from(sp.sib_mod(t), sorted(sp.cross[sib][t])))
            count += 1
    while out and out[-1] == "":
        out.pop()
    sp.header_stmt_count[sib] = count
    return out


def generate(sp: Split):
    for sib in sp.siblings:
        doc = sibling_docstring(sp, sib)
        imports = build_import_header(sp, sib)
        sp.import_lines[sib] = imports
        body = "".join(span_text(sp, st) for st in sp.owned(sib))
        sp.body_texts[sib] = body
        head = doc
        if imports:
            head += "\n" + "\n".join(imports) + "\n"
        sep = "" if leading_blank_lines(body) >= 1 else "\n"
        sp.texts[sib] = normalize_tail(head + sep + body)
    sp.facade_text = build_facade(sp)


def facade_comment(sp: Split) -> list:
    pattern = f"{sp.pkg_dir.name}/{sp.stem}_*" if sp.pkg else f"{sp.stem}_*"
    text = (f"FACADE. Since {sp.date} every name below is defined in one of the `{pattern}` "
            f"siblings, carved out of this file verbatim, and re-exported here explicitly -- "
            f"private names included -- so every `from {sp.modname} import X` and every "
            f"`{sp.stem}.X` keeps meaning what it meant (docs/design/DESIGN_MODULE_LAYOUT.md, "
            "\"Job 1: split behind facades\"). This module defines nothing of its own.")
    text2 = ("The import block above is RETAINED byte-for-byte, not pruned: tests monkeypatch "
             "names on this module, and a name that stops resolving here breaks them. A patch on "
             "this module is inert for a reader that moved to a sibling -- patch the sibling that "
             "reads the name, or use tests/helpers.py::patch_seam where several do.")
    out = []
    for para in (text, text2):
        out.extend("# " + l for l in textwrap.wrap(para, width=76, break_on_hyphens=False))
        out.append("#")
    out.pop()
    return out


def build_facade(sp: Split, exports: dict | None = None) -> str:
    exports = exports if exports is not None else sp.exports
    head = "".join(sp.lines[:sp.header.n])
    if not head.endswith("\n"):
        head += "\n"
    if split_keepends(head)[-1].strip():
        head += "\n"
    if leading_blank_lines("".join(reversed(split_keepends(head)))) < 2:
        head += "\n"
    parts = [head, "\n".join(facade_comment(sp)) + "\n"]
    for sib in sp.siblings:
        names = sorted(exports.get(sib, ()))
        if not names:
            continue
        parts.append("\n" if len(parts) == 2 else "")
        parts.append(f"from {sp.sib_mod(sib)} import (  # noqa: F401\n"
                     + "".join(f"    {n},\n" for n in names) + ")\n")
    kept = [st for st in sp.stmts if st.owner == FACADE]
    for st in kept:
        parts.append(span_text(sp, st))
    return normalize_tail("".join(parts))


# ---------------------------------------------------------------------------
# validation of the generated text (in memory; on disk after --apply)
# ---------------------------------------------------------------------------

def unbound_globals(text: str, filename: str) -> list:
    """Strict: every global a scope reads that the module itself never binds.

    Stricter than project_check.check_undefined_names, whose `known` set is
    every symbol of the module table -- so a name merely REFERENCED at module
    level counts as known there and is never reported.
    """
    top = symtable.symtable(text, filename, "exec")
    bound = {s.get_name() for s in top.get_symbols() if s.is_assigned() or s.is_imported()}
    stack = list(top.get_children())
    while stack:
        t = stack.pop()
        for s in t.get_symbols():
            if s.is_declared_global() and s.is_assigned():
                bound.add(s.get_name())
        stack.extend(t.get_children())
    bad = []

    def visit(t):
        for s in t.get_symbols():
            n = s.get_name()
            if not s.is_referenced():
                continue
            if (t is top or s.is_global()) and n not in bound \
                    and n not in BUILTIN_NAMES and n not in IMPLICIT_NAMES:
                bad.append((t.get_name(), t.get_lineno(), n))
        for c in t.get_children():
            visit(c)

    visit(top)
    return bad


def project_check_undefined(text: str, filename: str) -> list:
    """project_check.check_undefined_names' own algorithm, on one text."""
    if any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
           for n in ast.walk(ast.parse(text))):
        return []
    top = symtable.symtable(text, filename, "exec")
    known = ({s.get_name() for s in top.get_symbols()} | set(dir(builtins))
             | {"__file__", "__name__", "__doc__", "__package__", "__spec__",
                "__loader__", "__builtins__", "__debug__"})
    out = []

    def visit(scope):
        for s in scope.get_symbols():
            name = s.get_name()
            if s.is_global() and s.is_referenced() and not s.is_assigned() and name not in known:
                out.append(f"{scope.get_name()}() uses {name!r}")
        for c in scope.get_children():
            visit(c)

    visit(top)
    return out


def validate(sp: Split, texts: dict, facade_text: str, where: str):
    """Everything the generated (or written) files must satisfy."""
    diag = sp.diag
    h = sp.header
    trees = {}
    for sib, text in texts.items():
        fname = str(sp.sib_path(sib))
        try:
            trees[sib] = ast.parse(text, filename=fname)
            compile(text, fname, "exec", dont_inherit=True)
        except SyntaxError as exc:
            diag.error(f"[{where}] {sib}.py does not compile: {exc}")
    try:
        ftree = ast.parse(facade_text)
        compile(facade_text, str(sp.path), "exec", dont_inherit=True)
    except SyntaxError as exc:
        diag.error(f"[{where}] the facade does not compile: {exc}")
        return
    if len(trees) != len(texts):
        return
    # 1. statement-level verbatim: the moved statements' ASTs are the originals'
    for sib, tree in trees.items():
        k = sp.header_stmt_count[sib] + 1  # + docstring
        got = [ast.dump(n, include_attributes=False) for n in tree.body[k:]]
        want = [ast.dump(st.node, include_attributes=False) for st in sp.owned(sib)]
        if got != want:
            diag.error(f"[{where}] VERBATIM CHECK FAILED: {sib}.py's statements differ from the "
                       f"original's ({len(got)} vs {len(want)} statements)")
        body = texts[sib][len(texts[sib]) - len(normalize_tail(sp.body_texts[sib])):]
        if normalize_tail(sp.body_texts[sib]) and body != normalize_tail(sp.body_texts[sib]):
            diag.error(f"[{where}] VERBATIM CHECK FAILED: {sib}.py's body is not the concatenated spans")
    fh = [ast.dump(n, include_attributes=False) for n in ftree.body[:len(h.nodes)]]
    if fh != [ast.dump(n, include_attributes=False) for n in h.nodes] \
            or not facade_text.startswith("".join(sp.lines[:h.n]).rstrip("\n")):
        diag.error(f"[{where}] the facade does not start with the original header byte-for-byte")
    extra = [n for n in ftree.body[len(h.nodes):]
             if not isinstance(n, ast.ImportFrom)
             and not any(st.owner == FACADE and ast.dump(st.node) == ast.dump(n) for st in sp.stmts)]
    if extra:
        diag.error(f"[{where}] the facade defines something besides re-exports: "
                   f"{[kind_of(n) for n in extra]}")
    # 2. undefined names, strict and project_check's own
    for sib, text in texts.items():
        for scope, line, name in unbound_globals(text, f"{sib}.py"):
            diag.error(f"[{where}] {sib}.py: {scope}() (line {line}) reads {name!r}, which nothing in "
                       "the generated module binds (would be a NameError)")
        for msg in project_check_undefined(text, f"{sib}.py"):
            diag.error(f"[{where}] project_check.check_undefined_names would report {sib}.py: {msg}")
        bound_here = {s.get_name() for s in symtable.symtable(text, sib, "exec").get_symbols()
                      if s.is_assigned() or s.is_imported()}
        for st in sp.owned(sib):
            miss = (st.ann | st.ann_str) & sp.module_bound - bound_here - BUILTIN_NAMES
            miss -= {n for n, _ in sp.guarded[sib]}
            if miss:
                diag.error(f"[{where}] {sib}.py: {st.label} annotates with {sorted(miss)}, bound in "
                           f"the original module but not in {sib}.py (get_type_hints would fail)")
    for msg in project_check_undefined(facade_text, sp.path.name):
        diag.error(f"[{where}] project_check.check_undefined_names would report the facade: {msg}")
    # 3. family membership and import direction, with project_check's own functions
    pc = sp.pc
    if "facade_import_violations" in pc:
        for sib, tree in trees.items():
            for lineno, kind, module in pc["facade_import_violations"](
                    tree, pkg=sp.pkg_dir.name, stem=sp.stem, siblings=set(sp.siblings), inside=True,
                    module=f"{sp.pkg_dir.name}.{sib}"):
                diag.error(f"[{where}] {sib}.py:{lineno}: {kind} import of {module} "
                           "(project_check.check_facade_import_direction would fail)")
    members = facade_members(sp, ftree)
    if not set(sp.siblings) <= members:
        diag.error(f"[{where}] project_check.facade_siblings would not see "
                   f"{sorted(set(sp.siblings) - members)} as members of the family")
    elif where == "generated":
        family_extras(sp, members - set(sp.siblings))
    # 4. duplicate bodies inside the family (project_check._module_level_bodies)
    if "_module_level_bodies" in pc:
        seen = defaultdict(list)
        for sib, tree in trees.items():
            for name, body in pc["_module_level_bodies"](tree, texts[sib]).items():
                if len(body.splitlines()) >= pc.get("_DUPLICATE_MIN_LINES", 3):
                    seen[(name, body)].append(sib)
        for (name, _), sibs in seen.items():
            if len(sibs) > 1:
                diag.error(f"[{where}] {name!r} is defined identically in {sibs} "
                           "(check_cross_file_duplicate_definitions would fail)")
    # 5. what check_facade_patch_targets keys on
    if "_calls_and_imports" in pc:
        for sib, tree in trees.items():
            imported, called = pc["_calls_and_imports"](tree)
            sp.flagged[sib] = imported & called
    for sib in trees:
        # every name the generated import block binds in this sibling's globals
        names = set(sp.header_used[sib]) | {n for n, _ in sp.guarded[sib]} | set(sp.replicas.get(sib, ()))
        for target_names in sp.cross[sib].values():
            names |= set(target_names)
        for node in sp.compound_used[sib]:
            cb = module_bindings(node)
            names |= cb.binds | cb.cond
        sp.imported_into[sib] = names


def family_extras(sp: Split, extras: set):
    """Existing `<stem>_*` modules the header imports: project_check will count them as
    family members, so outside importers of them break once the family is registered."""
    if not extras:
        return
    diag = sp.diag
    registered = any(Path(home).name == sp.pkg_dir.name and stem == sp.stem
                     for home, stem in sp.pc.get("FACADE_FAMILIES", {}).values())
    if registered:
        diag.info(f"the facade family already includes {sorted(extras)} (registered in "
                  "FACADE_FAMILIES); the new siblings join it")
        return
    importers = defaultdict(list)
    inside_out = []
    dirs = [d for d in sp.root.iterdir() if d.is_dir() and not d.name.startswith(".")
            and d.name not in ("node_modules", "output", "backdrops", "__pycache__")]
    pat = re.compile(r"\b(" + "|".join(re.escape(e) for e in sorted(extras)) + r")\b")
    pc_viol = sp.pc.get("facade_import_violations")
    for d in dirs:
        for path in d.rglob("*.py"):
            if "__pycache__" in path.parts or path == sp.path:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not pat.search(text):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            rel = path.relative_to(sp.root).as_posix()
            is_member = path.parent == sp.pkg_dir and path.stem in extras
            if pc_viol is not None:
                for lineno, kind, module in pc_viol(tree, pkg=sp.pkg_dir.name, stem=sp.stem,
                                                    siblings=set(sp.siblings) | extras,
                                                    inside=is_member,
                                                    is_test=path.parent.name == "tests",
                                                    module=".".join(path.relative_to(
                                                        sp.root).with_suffix("").parts)):
                    if kind == "outside-in" and module.rpartition(".")[2] in extras:
                        importers[module].append(f"{rel}:{lineno}")
                    elif kind == "inside-out":
                        inside_out.append(f"{rel}:{lineno}")
    detail = "; ".join(f"{m} imported directly by {len(v)} site(s) ({', '.join(v[:4])}{' ...' if len(v) > 4 else ''})"
                       for m, v in sorted(importers.items()))
    diag.warn(f"the header imports existing module(s) {sorted(extras)} whose names start with "
              f"{sp.stem + '_'!r}: project_check.facade_siblings will count them as members of the "
              f"{sp.modname} family once it is registered in FACADE_FAMILIES. "
              + (f"That turns these into outside-in violations: {detail}. " if detail else
                 "Nothing outside imports them directly, so registering is safe. ")
              + (f"Inside-out (they import the facade): {inside_out}. " if inside_out else ""))


def facade_members(sp: Split, ftree) -> set:
    """project_check.facade_siblings' reading, applied to a facade that may not exist yet."""
    found = set()
    prefix = sp.stem + "_"
    for node in ast.walk(ftree):
        if isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            continue
        for name in names:
            tail = name.rpartition(".")[2]
            if tail.startswith(prefix) and (tail in sp.siblings or (sp.pkg_dir / (tail + ".py")).is_file()):
                found.add(tail)
    return found


# ---------------------------------------------------------------------------
# anatomy: contract, repoints, pins
# ---------------------------------------------------------------------------

def use_anatomy(sp: Split, anatomy: dict):
    diag = sp.diag
    if anatomy.get("lines") not in (None, len(sp.lines)):
        diag.warn(f"the anatomy saw {anatomy.get('lines')} lines, the file has {len(sp.lines)}: it is "
                  "STALE -- regenerate it before trusting the repoint table")
    body_names = set()
    for st in sp.stmts:
        body_names.update(st.names)
    anat_names = {s["name"] for s in anatomy.get("symbols", [])}
    missing = sorted(anat_names - body_names - sp.header.all_names())
    if missing:
        diag.warn(f"anatomy lists symbols the module no longer has: {missing[:10]}")
    new = sorted({st.names[0] for st in sp.stmts if st.kind in ("def", "async def", "class")} - anat_names)
    if new:
        diag.warn(f"module has defs the anatomy does not list (stale anatomy): {new[:10]}")
    # contract: every name the repo reads off the module must still resolve
    facade_names = sp.header.runtime_names() | set().union(*sp.exports.values()) | {
        n for st in sp.stmts if st.owner == FACADE for n in st.b.all_bound()}
    original = sp.final_ns
    contract = {"from_imports": sorted(anatomy.get("from_imports", {})),
                "attr_uses": sorted(anatomy.get("attr_uses", {}))}
    unresolved, preexisting = [], []
    for kind in ("from_imports", "attr_uses"):
        for n in contract[kind]:
            if n.startswith("__") and n.endswith("__"):
                continue
            if n in facade_names:
                continue
            (unresolved if n in original else preexisting).append(f"{n} ({kind})")
    for u in unresolved:
        diag.error(f"CONTRACT: the repository reads {u} off {sp.modname} and the new facade "
                   "would not provide it")
    for u in preexisting:
        diag.warn(f"CONTRACT: the repository reads {u} off {sp.modname}, which the ORIGINAL does "
                  "not bind either (pre-existing)")
    sp.contract = {"from_imports": len(contract["from_imports"]),
                   "attr_uses": len(contract["attr_uses"]),
                   "unresolved": unresolved, "preexisting": preexisting}
    # repoint table
    attr_files = anatomy.get("attr_use_files", {})
    by_name = defaultdict(list)
    for f, line, name, form in anatomy.get("patch_sites", []):
        by_name[name].append((f, line, form))
    plan_rp = {(r.get("file"), r.get("line")): r for r in sp.plan.get("repoints", []) or []}
    seen_plan = set()
    rows = []
    for name, sites in sorted(by_name.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        readers = []
        for sib in sp.siblings:
            in_globals = name in sp.defined.get(sib, ()) or name in sp.imported_into.get(sib, ())
            reads = any(name in (st.refs | st.class_local) for st in sp.owned(sib))
            if in_globals and reads:
                how = "defines" if name in sp.defined.get(sib, ()) else "imports"
                readers.append({"sibling": sib, "module": sp.sib_mod(sib), "how": how,
                                "imported_and_called": name in sp.flagged.get(sib, set())})
        home = sp.last_owner.get(name) or ("header import" if name in sp.header.runtime_names() else
                                           "not bound by the module")
        outsiders = attr_files.get(name, [])
        if not readers:
            verdict = "no repoint needed (only the facade/outsiders read it)"
        elif len(readers) == 1:
            verdict = f"repoint to {readers[0]['module']}"
        else:
            verdict = ("repoint to EACH of " + ", ".join(r["module"] for r in readers)
                       + " -- use tests/helpers.py::patch_seam")
        if readers and outsiders:
            verdict += (f"; outsiders also read `{sp.stem}.{name}` at call time "
                        f"({len(outsiders)} file(s)), so keep a patch on the facade too or use patch_seam")
        plan_status = []
        for f, line, form in sites:
            r = plan_rp.get((f, line))
            if r is not None:
                seen_plan.add((f, line))
            if readers:
                targets = {x["module"] for x in readers}
                if r is None:
                    plan_status.append(f"{f}:{line} MISSING from plan.repoints")
                elif r.get("to") not in targets:
                    plan_status.append(f"{f}:{line} plan says {r.get('to')}, readers are {sorted(targets)}")
            elif r is not None and r.get("kind") in (None, "setattr"):
                plan_status.append(f"{f}:{line} plan repoints to {r.get('to')} but no sibling reads it")
        any_flag = any(x["imported_and_called"] for x in readers)
        site_rows = [{"site": f"{f}:{l}" + ("" if form == "attr" else f" [{form}]"), "form": form,
                      "pc_flags": bool(readers) and form == "attr" and any_flag} for f, l, form in sites]
        rows.append({"name": name, "sites": [s["site"] for s in site_rows], "site_rows": site_rows,
                     "home": home, "readers": readers, "verdict": verdict,
                     "outsider_files": outsiders, "plan": plan_status})
    sp.repoint_rows = rows
    # pins: list for manual repoint, with the moved names each pinning file mentions
    moved = {n: st.owner for st in sp.stmts if st.owner not in (None, FACADE) for n in st.names}
    pins = []
    for kind in ("source_pins", "file_pins"):
        for f, line, text in anatomy.get(kind, []):
            mentions = []
            p = sp.root / f
            try:
                content = p.read_text(encoding="utf-8")
                counts = Counter(m for m in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", content)
                                 if m in moved and len(m) >= 4)
                mentions = [f"{m} -> {moved[m]}" for m, _ in counts.most_common(6)]
            except OSError:
                pass
            r = plan_rp.get((f, line))
            if r is not None:
                seen_plan.add((f, line))
            pins.append({"kind": kind, "site": f"{f}:{line}", "text": text,
                         "mentions": mentions,
                         "plan": (f"plan repoints to {r.get('to')}" if r else "MISSING from plan.repoints")})
    sp.pin_rows = pins
    for key, r in plan_rp.items():
        if key not in seen_plan:
            diag.warn(f"plan.repoints names {key[0]}:{key[1]} ({r.get('name')}), which is no patch "
                      "site or pin in the anatomy")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def render_report(sp: Split, mode: str, include_info: bool) -> str:
    out = []
    w = out.append
    d = sp.diag
    w(f"split_module {mode}: {sp.rel} ({sp.modname}) -> {len(sp.siblings)} siblings + facade")
    w(f"  header (retained byte-for-byte): lines 1-{sp.header.n}, {len(sp.header.nodes)} statements; "
      f"body: lines {sp.header.n + 1}-{len(sp.lines)}, {len(sp.stmts)} top-level statements")
    w("")
    w("MODULE TABLE")
    rows = [("sibling", "lines", "stmts", "header imports used", "sibling imports")]
    for sib in sp.siblings:
        text = sp.texts.get(sib, "")
        hu = sp.header_used.get(sib, [])
        hu_s = f"{len(hu)}: " + ", ".join(hu[:6]) + (" ..." if len(hu) > 6 else "") if hu else "0"
        if sp.guarded.get(sib):
            hu_s += f" (+{len(sp.guarded[sib])} guarded)"
        cx = sp.cross.get(sib, {})
        cx_s = ", ".join(f"{t} ({len(v)})" for t, v in cx.items()) or "-"
        rows.append((sib, str(len(split_keepends(text))), str(len(sp.owned(sib))), hu_s, cx_s))
    nexp = sum(len(v) for v in sp.exports.values())
    rows.append(("<facade>", str(len(split_keepends(sp.facade_text))),
                 str(sum(1 for s in sp.stmts if s.owner == FACADE)),
                 f"{len(sp.header.all_names())} retained", f"{nexp} re-exports"))
    rows = [tuple(c if i != 3 or len(c) <= 58 else c[:55] + "..." for i, c in enumerate(r)) for r in rows]
    widths = [max(len(r[i]) for r in rows) for i in range(5)]
    for r in rows:
        w("  " + "  ".join(c.ljust(widths[i]) if i < 4 else c for i, c in enumerate(r)))
    w("")
    w("DAG (leaf-first; each sibling -> the siblings it imports)")
    for sib in sp.order_topo or sp.siblings:
        w(f"  {sib:<24} -> {', '.join(t for t in sp.siblings if t in sp.cross.get(sib, {})) or '[]'}")
    w(f"  plan order: {', '.join(sp.siblings)}")
    w("")
    w(f"RE-EXPORTS: {nexp} names "
      + ", ".join(f"{sib} {len(sp.exports.get(sib, []))}" for sib in sp.siblings)
      + f" (private: {sum(1 for v in sp.exports.values() for n in v if n.startswith('_'))})")
    if sp.contract:
        c = sp.contract
        w(f"CONTRACT (anatomy): {c['from_imports']} names imported from the module, "
          f"{c['attr_uses']} read as attributes: "
          + ("all resolve on the new facade" if not c["unresolved"] else
             f"{len(c['unresolved'])} UNRESOLVED") +
          (f"; {len(c['preexisting'])} pre-existing misses" if c["preexisting"] else ""))
    w("")
    w(f"ERRORS ({len(d.errors)})")
    for m in d.errors:
        w("  E " + m)
    w(f"WARNINGS ({len(d.warnings)})")
    for m in d.warnings:
        w("  W " + m)
    if include_info:
        w(f"INFO ({len(d.infos)})")
        for m in d.infos:
            w("  I " + m)
    else:
        w(f"INFO ({len(d.infos)}) suppressed")
    if sp.repoint_rows or sp.pin_rows:
        w("")
        w(f"REPOINT TABLE ({sum(len(r['sites']) for r in sp.repoint_rows)} monkeypatch sites, "
          f"{len(sp.repoint_rows)} names)")
        for r in sp.repoint_rows:
            w(f"  {r['name']}  [{len(r['sites'])} site(s); defined: {r['home']}]")
            w(f"    -> {r['verdict']}")
            for x in r["readers"]:
                flag = ("imported & called: the shape project_check.check_facade_patch_targets detects"
                        if x["imported_and_called"] else
                        "project_check CANNOT see this reader -- a facade patch is SILENTLY inert for it")
                w(f"       reader {x['module']} ({x['how']} it): {flag}")
            if r["readers"]:
                flagged = [s["site"] for s in r["site_rows"] if s["pc_flags"]]
                silent = [s["site"] for s in r["site_rows"] if not s["pc_flags"]]
                if flagged:
                    w(f"       project_check will report {len(flagged)}/{len(r['sites'])} site(s): "
                      f"{'; '.join(flagged[:6])}{' ...' if len(flagged) > 6 else ''}")
                if silent:
                    w(f"       SILENT sites (nothing will report them; string-form patches are never "
                      f"read by project_check): {'; '.join(silent[:6])}{' ...' if len(silent) > 6 else ''}")
                if flagged and any(not x["imported_and_called"] for x in r["readers"]):
                    w("       NOTE: fixing only what project_check reports would miss the silent reader(s) above")
            else:
                w(f"       sites: {'; '.join(r['sites'][:8])}{' ...' if len(r['sites']) > 8 else ''}")
            for p in r["plan"]:
                w(f"       plan: {p}")
        w("")
        w(f"PINS FOR MANUAL REPOINT ({len(sp.pin_rows)})")
        for p in sp.pin_rows:
            w(f"  {p['kind']}: {p['site']} {p['text']}  [{p['plan']}]")
            if p["mentions"]:
                w(f"    the file names moved symbols: {', '.join(p['mentions'])}")
    w("")
    return "\n".join(out)


def report_json(sp: Split, mode: str, status: str) -> dict:
    return {
        "mode": mode, "status": status, "module": sp.rel, "modname": sp.modname,
        "header_lines": sp.header.n, "statements": len(sp.stmts),
        "siblings": [{"name": s, "lines": len(split_keepends(sp.texts.get(s, ""))),
                      "statements": len(sp.owned(s)), "header_imports": sp.header_used.get(s, []),
                      "guarded": [n for n, _ in sp.guarded.get(s, [])],
                      "sibling_imports": {t: sorted(v) for t, v in sp.cross.get(s, {}).items()},
                      "exports": sp.exports.get(s, [])} for s in sp.siblings],
        "dag_order": sp.order_topo, "errors": sp.diag.errors, "warnings": sp.diag.warnings,
        "infos": sp.diag.infos, "repoints": sp.repoint_rows, "pins": sp.pin_rows,
        "contract": sp.contract, "timings": sp.timings,
    }


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

SNAPSHOT = r'''
import importlib, json, sys
try:
    mod = importlib.import_module(sys.argv[1])
    print("@@SPLIT_MODULE@@" + json.dumps({"names": sorted(vars(mod)), "file": getattr(mod, "__file__", None)}))
except BaseException:
    import traceback
    print("@@SPLIT_MODULE@@" + json.dumps({"error": traceback.format_exc()}))
'''

VERIFY = r'''
import importlib, json, sys
req = json.loads(sys.stdin.read())
out = {"missing": [], "not_same": [], "sibling_missing": [], "extra": [], "error": None}
try:
    facade = importlib.import_module(req["facade"])
    mods = {}
    for name in req["former"]:
        if not hasattr(facade, name):
            out["missing"].append(name)
            continue
        owner = req["owners"].get(name)
        if not owner:
            continue
        if owner not in mods:
            mods[owner] = importlib.import_module(owner)
        m = mods[owner]
        if not hasattr(m, name):
            out["sibling_missing"].append([name, owner])
        elif getattr(m, name) is not getattr(facade, name):
            out["not_same"].append([name, owner])
    for sib in req["siblings"]:
        if sib not in mods:
            mods[sib] = importlib.import_module(sib)
    for name, sibs in req.get("replicas", {}).items():
        for sib in sibs:
            if getattr(mods[sib], name, None) is not getattr(facade, name, object()):
                out["not_same"].append([name, sib])
    now = [n for n in vars(facade) if not (n.startswith("__") and n.endswith("__"))]
    out["extra"] = sorted(set(now) - set(req["former"]))
    out["facade_file"] = facade.__file__
except BaseException:
    import traceback
    out["error"] = traceback.format_exc()
print("@@SPLIT_MODULE@@" + json.dumps(out))
'''


def run_py(python: str, root: Path, code: str, args=(), stdin: str | None = None) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    tmpdir = tempfile.mkdtemp(prefix="split_module_db_")
    env["ENGINE_DB"] = os.path.join(tmpdir, "verify.db")   # never the developer's database
    proc = subprocess.run([python, "-c", code, *args], cwd=str(root), env=env, input=stdin,
                          capture_output=True, text=True, timeout=600)
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    return {"error": f"subprocess exited {proc.returncode} without a result\nstdout:\n"
                     f"{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}"}


def apply_split(sp: Split, python: str, force: bool, backup_root: Path) -> int:
    diag = sp.diag
    paths = {sib: sp.sib_path(sib) for sib in sp.siblings}
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing and not force:
        print(f"REFUSED: sibling file(s) already exist: {existing} (pass --force to overwrite)")
        return 1
    print(f"snapshotting the ORIGINAL {sp.modname} namespace in a subprocess ...")
    snap = run_py(python, sp.root, SNAPSHOT, [sp.modname])
    if "error" in snap:
        print("REFUSED: the original module does not import cleanly, so the split cannot be "
              "verified:\n" + snap["error"])
        return 1
    runtime = set(snap["names"])
    def nd(names):
        return {n for n in names if not (n.startswith("__") and n.endswith("__"))}
    exported = set().union(*sp.exports.values())
    facade_own = {n for st in sp.stmts if st.owner == FACADE for n in st.b.all_bound()}
    unknown = nd(runtime) - sp.header.runtime_names() - exported - facade_own
    if unknown:
        print(f"REFUSED: the original binds {sorted(unknown)} at runtime by means the static "
              "analysis cannot see (globals()[...] = ..., setattr on the module, a header side "
              "effect); the facade would lose them")
        return 1
    phantom = {n for n in exported if n not in runtime}
    exports = sp.exports
    if phantom:
        diag.warn(f"not bound at runtime, dropped from the facade's re-exports: {sorted(phantom)}")
        exports = {s: [n for n in v if n not in phantom] for s, v in sp.exports.items()}
        sp.facade_text = build_facade(sp, exports)
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix=f"{sp.stem}-{sp.date}-", dir=str(backup_root)))
    backup = backup_dir / (sp.stem + ".py.orig")
    backup.write_text(sp.src, encoding="utf-8")
    written = []
    for sib in sp.siblings:
        paths[sib].write_text(sp.texts[sib], encoding="utf-8")
        written.append(paths[sib])
    sp.path.write_text(sp.facade_text, encoding="utf-8")
    print(f"wrote {len(written)} siblings and rewrote {sp.rel} (original saved to {backup})")
    # re-validate exactly what is on disk
    disk = {sib: paths[sib].read_text(encoding="utf-8") for sib in sp.siblings}
    before = len(diag.errors)
    validate(sp, disk, sp.path.read_text(encoding="utf-8"), "on disk")
    owners = {n: sp.sib_mod(s) for s, v in exports.items() for n in v}
    former = sorted(nd(runtime) | {n for n in exported - phantom if n in runtime})
    reps = defaultdict(list)
    for s in sp.siblings:
        for n in sp.replicas.get(s, ()):
            reps[n].append(sp.sib_mod(s))
    req = {"facade": sp.modname, "former": former, "owners": owners,
           "siblings": [sp.sib_mod(s) for s in sp.siblings], "replicas": dict(reps)}
    print("re-importing the facade and every sibling in a fresh subprocess ...")
    res = run_py(python, sp.root, VERIFY, stdin=json.dumps(req))
    problems = []
    if res.get("error"):
        problems.append("import failed:\n" + res["error"])
    for key, label in (("missing", "former names missing on the facade"),
                       ("sibling_missing", "names missing on their sibling"),
                       ("not_same", "facade name is NOT the sibling's object"),
                       ("extra", "names on the facade that the original did not have")):
        if res.get(key):
            problems.append(f"{label}: {res[key]}")
    run_disk_checks(sp)
    if problems or len(diag.errors) > before:
        print("VERIFICATION FAILED")
        for p in problems:
            print("  - " + p)
        for e in diag.errors[before:]:
            print("  - " + e)
        print("To revert:")
        print(f"  git checkout -- {sp.rel}        (or: cp {backup} {sp.path})")
        print("  rm " + " ".join(str(p) for p in written))
        return 3
    print(f"VERIFIED: {len(former)} former names resolve on {sp.modname}; {len(owners)} moved "
          f"names are the very objects their siblings define; no extra names; original at {backup}")
    return 0


def run_disk_checks(sp: Split):
    """project_check's two facade rules, run from its own source against the written tree."""
    pc, diag = sp.pc, sp.diag
    if not all(k in pc for k in PC_DISK):
        return
    family = sp.modname
    pc["FACADE_FAMILIES"] = {family: (sp.pkg_dir, sp.stem)}
    pc["ROOT"] = sp.root.resolve()
    pkg_files = sorted(sp.pkg_dir.glob("*.py"))
    pc["engine_python_paths"] = lambda: pkg_files
    for fn in PC_DISK:
        errs = []
        try:
            pc[fn](errs)
        except Exception as exc:  # pragma: no cover
            diag.warn(f"project_check.{fn} could not run here: {exc!r}")
            continue
        if fn == "check_facade_patch_targets":
            for e in errs:
                diag.warn("project_check.check_facade_patch_targets now reports (repoint it): " + e)
            if not errs:
                diag.info("project_check.check_facade_patch_targets: no inert facade patches found")
        else:
            for e in errs:
                diag.error(f"project_check.{fn}: {e}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def backup_root(args, sp: Split) -> Path:
    if args.backup_dir:
        return args.backup_dir.resolve()
    beside = args.plan.resolve().parent / "split_backups"
    if inside(beside, sp.root):
        return Path(tempfile.gettempdir()) / "split_backups"
    return beside


def emit(sp: Split, out: Path):
    """Write the generated files for review, never inside the import root."""
    if inside(out, sp.root):
        sp.diag.error(f"--emit-dir {out} is inside --root {sp.root}; refusing to write there")
        return
    base = out / Path(sp.rel).parent
    base.mkdir(parents=True, exist_ok=True)
    for sib in sp.siblings:
        (base / f"{sib}.py").write_text(sp.texts[sib], encoding="utf-8")
    (base / Path(sp.rel).name).write_text(sp.facade_text, encoding="utf-8")
    print(f"[emit] generated files written under {base}")


def list_statements(sp: Split):
    print(f"{sp.rel}: header 1-{sp.header.n}; {len(sp.stmts)} statements after it")
    for st in sp.stmts:
        key = ", ".join(st.names) if st.names else st.key
        span = st.span or (st.first, st.last)
        print(f"  {span[0]:>6}-{span[1]:<6} {st.kind:<10} {key:<40} "
              f"{snippet_of(sp.lines, st.first, st.last, 50) if not st.names else ''}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--anatomy", type=Path)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--list", action="store_true")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                    help="import root the plan's module path is relative to (default: the repo)")
    ap.add_argument("--python", default=str(DEFAULT_PYTHON),
                    help="interpreter for the --apply import checks (default: the repo .venv)")
    ap.add_argument("--force", action="store_true", help="overwrite existing sibling files")
    ap.add_argument("--date", default=_dt.date.today().isoformat())
    ap.add_argument("--auto-attach", action="store_true",
                    help="attach unassigned non-definition statements (@line:N) to the suggested "
                         "sibling with a WARNING instead of refusing")
    ap.add_argument("--json-report", type=Path)
    ap.add_argument("--emit-dir", type=Path,
                    help="--check: also write the generated siblings and facade under this "
                         "directory (must be outside --root) for review/diffing")
    ap.add_argument("--backup-dir", type=Path,
                    help="--apply: where the original module is saved (default: "
                         "split_backups/ beside the plan, or the system temp dir if the plan "
                         "lives inside --root)")
    ap.add_argument("--no-info", action="store_true", help="suppress INFO lines in the report")
    ap.add_argument("--debug-drop-span", metavar="KEY",
                    help="testing: drop one statement's span before the verbatim assertion")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    diag = Diag()
    try:
        plan = load_plan(args.plan)
        sp = build_split(plan, args.root.resolve(), args.date, diag)
    except PlanError as exc:
        print(f"PLAN ERROR: {exc}")
        return 2
    if args.list:
        list_statements(sp)
        return 0
    sp.timings["parse"] = round(time.perf_counter() - t0, 3)
    try:
        assign_owners(sp, args.auto_attach)
    except PlanError as exc:
        print(f"PLAN ERROR: {exc}")
        return 2
    spans = [st.span for st in sp.stmts if st.span is not None]
    if args.debug_drop_span:
        spans = [st.span for st in sp.stmts if st.span is not None
                 and args.debug_drop_span not in (st.key, *st.names)]
        print(f"[debug] dropped {len(sp.stmts) - len(spans)} span(s) for {args.debug_drop_span!r}")
    try:
        verify_verbatim(sp.lines, sp.header.n, spans)
    except VerbatimError as exc:
        print(str(exc))
        print("REFUSED: the move would not be verbatim")
        return 1
    sp.pc = load_project_check(args.root, diag)
    t1 = time.perf_counter()
    analyse(sp)
    check_dag(sp)
    check_effect_order(sp)
    sp.timings["analyse"] = round(time.perf_counter() - t1, 3)
    t2 = time.perf_counter()
    generate(sp)
    validate(sp, sp.texts, sp.facade_text, "generated")
    sp.timings["generate+validate"] = round(time.perf_counter() - t2, 3)
    if args.anatomy:
        try:
            anatomy = json.loads(args.anatomy.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"PLAN ERROR: cannot read anatomy {args.anatomy}: {exc}")
            return 2
        if anatomy.get("path") not in (None, sp.rel):
            diag.warn(f"anatomy describes {anatomy.get('path')}, the plan splits {sp.rel}")
        use_anatomy(sp, anatomy)
    mode_name = "--apply" if args.apply else "--check"
    status = 0
    if args.emit_dir and not args.apply:
        emit(sp, args.emit_dir.resolve())
    if args.apply and not diag.errors:
        print(render_report(sp, mode_name, not args.no_info))
        marks = (len(diag.errors), len(diag.warnings), len(diag.infos))
        status = apply_split(sp, args.python, args.force, backup_root(args, sp))
        new = ([("E", m) for m in diag.errors[marks[0]:]] + [("W", m) for m in diag.warnings[marks[1]:]]
               + ([("I", m) for m in diag.infos[marks[2]:]] if not args.no_info else []))
        if new:
            print(f"DIAGNOSTICS RAISED DURING --apply ({len(new)})")
            for tag, m in new:
                print(f"  {tag} {m}")
        print("RESULT: " + {0: "APPLIED and VERIFIED", 1: "REFUSED -- nothing was written",
                            3: "WRITTEN BUT VERIFICATION FAILED -- revert as shown above"}.get(status, str(status)))
    else:
        print(render_report(sp, mode_name, not args.no_info))
        if diag.errors:
            status = 1
            print(f"RESULT: REFUSED -- {len(diag.errors)} error(s)"
                  + ("; nothing was written" if args.apply else ""))
        else:
            print("RESULT: OK (check mode: nothing written to the module tree)" if not args.apply else "")
    sp.timings["total"] = round(time.perf_counter() - t0, 3)
    print(f"time: {sp.timings}")
    if args.json_report:
        args.json_report.write_text(json.dumps(report_json(
            sp, mode_name, {0: "ok", 1: "refused", 3: "verification failed"}.get(status, str(status))),
            indent=1, default=list), encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
