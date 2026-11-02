#!/usr/bin/env python3
"""The anatomy of one module, read before it is split behind a facade.

    python tools/module_anatomy.py agents/perception.py
    python tools/module_anatomy.py agents/common.py agents/composer.py --json DIR

What a split plan has to know about the module it carves, and cannot safely
guess (`docs/design/DESIGN_MODULE_LAYOUT.md`, "split behind facades"): its
section markers, every top-level symbol with its line range, module-level
mutable state and `global` writers, deferred imports, the intra-module
reference graph and its connected components, and the module's EXTERNAL
contract -- which names the rest of the repository imports from it, which
attributes are used through the module object, which tests monkeypatch it (the
attribute AND the string spelling), and which tests pin its source text
(`inspect.getsource(<module>)`) or its file (`<module>.__file__`, `"<stem>.py"`
literals). Those last three are a split's blast radius: a patch on a name whose
reader moved goes inert, and a source pin reads the wrong file.

Written for the 2026-11-01 review, which split `agents/common.py`,
`agents/composer.py` and `agents/perception.py` from these reports with
`tools/split_module.py`; `docs/design/SPLIT_COMMON.md` records the method and
what the reports missed (relative imports, for one).

Read-only. Prints a Markdown report to stdout; with `--json`, writes
`<stem>.json` and `<stem>.md` per module into the directory named instead. A
relative path is read against the repository root, which is this file's
parent's parent -- never a path written down here.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

#: The checkout this file sits in.
ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", ".venv-browser", ".claude", "output", "node_modules",
             "__pycache__", ".git", "demo"}

MUTABLE_CTORS = {"dict", "list", "set", "defaultdict", "Counter", "Lock",
                 "RLock", "ContextVar", "deque", "OrderedDict", "Event",
                 "Semaphore", "BoundedSemaphore", "Queue", "WeakKeyDictionary",
                 "WeakValueDictionary", "LRUCache", "TTLCache"}


_TREES = {}


def parsed(p: Path):
    if p not in _TREES:
        try:
            _TREES[p] = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            _TREES[p] = None
    return _TREES[p]


def repo_python_files():
    for p in ROOT.rglob("*.py"):
        parts = set(p.relative_to(ROOT).parts)
        if parts & SKIP_DIRS:
            continue
        yield p


def _ctor_name(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def is_mutable_value(val) -> bool:
    if isinstance(val, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp,
                        ast.SetComp)):
        return True
    if isinstance(val, ast.Call) and _ctor_name(val) in MUTABLE_CTORS:
        return True
    return False


def anatomy(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    rel = path.relative_to(ROOT).as_posix()
    modname = ".".join(path.relative_to(ROOT).with_suffix("").parts)
    stem = path.stem
    pkg = path.parent.name

    # --- section markers -------------------------------------------------
    markers = []
    marker_re = re.compile(r"^\s*#\s*(?:-{3,}|={3,}|#{3,})\s*(.*?)\s*(?:-{3,}|={3,}|#{3,})?\s*$")
    for i, line in enumerate(lines, 1):
        m = marker_re.match(line)
        if m and m.group(1).strip() and not set(m.group(1).strip()) <= set("-=# "):
            markers.append((i, m.group(1).strip()))

    # --- top-level symbols ----------------------------------------------
    syms = []
    mod_imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "def"
            start = node.lineno
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list)
            syms.append({"name": node.name, "kind": kind, "start": start,
                         "end": node.end_lineno, "lines": node.end_lineno - start + 1})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    kind = "MUTABLE" if is_mutable_value(node.value) else "const"
                    syms.append({"name": t.id, "kind": kind, "start": node.lineno,
                                 "end": node.end_lineno,
                                 "lines": node.end_lineno - node.lineno + 1})
        elif isinstance(node, ast.Import):
            for a in node.names:
                mod_imports.append((node.lineno, "import", a.name, a.asname))
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                mod_imports.append((node.lineno, "from " + (node.module or ""),
                                    a.name, a.asname))

    top_names = {s["name"] for s in syms}
    imported_names = {a[3] or a[2].split(".")[0] for a in mod_imports}

    # --- deferred imports + global writers + intra refs -------------------
    deferred = []
    global_writers = defaultdict(list)
    refs = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        used = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in top_names and sub.id != node.name:
                used.add(sub.id)
            elif isinstance(sub, ast.Global):
                for g in sub.names:
                    global_writers[g].append(node.name)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)) and sub is not node:
                if isinstance(sub, ast.ImportFrom):
                    deferred.append((sub.lineno, node.name, sub.module or "",
                                     [a.name for a in sub.names]))
                else:
                    deferred.append((sub.lineno, node.name, ",".join(a.name for a in sub.names), []))
        refs[node.name] = sorted(used)

    # connected components over the undirected reference graph (defs/classes only)
    adj = defaultdict(set)
    for a, bs in refs.items():
        for b in bs:
            if b in refs:
                adj[a].add(b)
                adj[b].add(a)
    seen = set()
    components = []
    for name in refs:
        if name in seen:
            continue
        stack, comp = [name], []
        seen.add(name)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(sorted(comp, key=lambda n: next(s["start"] for s in syms if s["name"] == n)))
    components.sort(key=len, reverse=True)

    # --- external contract -------------------------------------------------
    from_imports = defaultdict(lambda: Counter())      # name -> Counter(prod/test)
    from_import_files = defaultdict(set)
    attr_uses = defaultdict(lambda: Counter())         # attr -> Counter(prod/test)
    attr_use_files = defaultdict(set)
    module_importers = {"prod": set(), "test": set()}
    patch_sites = []        # (file, line, name, form)
    source_pins = []        # (file, line, text)
    file_pins = []          # (file, line, text)
    star_imports = []

    short_from = f"from {pkg} import {stem}"
    for p in repo_python_files():
        if p == path:
            continue
        t = parsed(p)
        if t is None:
            continue
        prel = p.relative_to(ROOT).as_posix()
        side = "test" if prel.startswith("tests/") else "prod"
        aliases = set()
        for node in ast.walk(t):
            if isinstance(node, ast.ImportFrom):
                if node.module == modname:
                    for a in node.names:
                        if a.name == "*":
                            star_imports.append(prel)
                        from_imports[a.name][side] += 1
                        from_import_files[a.name].add(prel)
                elif node.module == pkg or (node.module or "").endswith("." + pkg) or node.module == modname.rsplit(".", 1)[0]:
                    for a in node.names:
                        if a.name == stem:
                            aliases.add(a.asname or stem)
                            module_importers[side].add(prel)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == modname:
                        aliases.add(a.asname or modname.split(".")[0])
                        module_importers[side].add(prel)
        # attribute uses through the module object
        if aliases:
            for node in ast.walk(t):
                if isinstance(node, ast.Attribute):
                    base = node.value
                    # alias.attr   or   pkg.stem.attr
                    if isinstance(base, ast.Name) and base.id in aliases and modname.split(".")[0] not in aliases:
                        attr_uses[node.attr][side] += 1
                        attr_use_files[node.attr].add(prel)
                    elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                            and base.value.id == modname.split(".")[0] and base.attr == stem:
                        attr_uses[node.attr][side] += 1
                        attr_use_files[node.attr].add(prel)
                    elif isinstance(base, ast.Name) and base.id in aliases and base.id == stem:
                        attr_uses[node.attr][side] += 1
                        attr_use_files[node.attr].add(prel)
        # patch sites, source pins, file pins (tests and prod alike)
        for node in ast.walk(t):
            if isinstance(node, ast.Call):
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
                if fname == "setattr" and len(node.args) >= 2:
                    tgt, attr = node.args[0], node.args[1]
                    if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
                        if isinstance(tgt, ast.Name) and tgt.id in aliases:
                            patch_sites.append((prel, node.lineno, attr.value, "attr"))
                        elif isinstance(tgt, ast.Attribute) and tgt.attr == stem:
                            patch_sites.append((prel, node.lineno, attr.value, "attr"))
                    if isinstance(tgt, ast.Constant) and isinstance(tgt.value, str) \
                            and tgt.value.startswith(modname + "."):
                        patch_sites.append((prel, node.lineno, tgt.value[len(modname) + 1:], "string"))
                if fname in {"patch", "object"} and node.args:
                    a0 = node.args[0]
                    if isinstance(a0, ast.Constant) and isinstance(a0.value, str) \
                            and a0.value.startswith(modname + "."):
                        patch_sites.append((prel, node.lineno, a0.value[len(modname) + 1:], "mock.patch"))
                if fname == "getsource" and node.args:
                    a0 = node.args[0]
                    if isinstance(a0, ast.Name) and a0.id in aliases:
                        source_pins.append((prel, node.lineno, f"inspect.getsource({a0.id})"))
                    elif isinstance(a0, ast.Attribute) and isinstance(a0.value, ast.Name) \
                            and a0.value.id in aliases:
                        source_pins.append((prel, node.lineno, f"getsource({a0.value.id}.{a0.attr})"))
            elif isinstance(node, ast.Attribute) and node.attr == "__file__":
                base = node.value
                if isinstance(base, ast.Name) and base.id in aliases:
                    file_pins.append((prel, node.lineno, f"{base.id}.__file__"))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value == stem + ".py" or node.value.endswith("/" + stem + ".py"):
                    file_pins.append((prel, node.lineno, repr(node.value)))

    return {
        "module": modname, "path": rel, "lines": len(lines), "markers": markers,
        "symbols": syms, "module_imports": mod_imports, "deferred_imports": deferred,
        "global_writers": dict(global_writers), "refs": refs, "components": components,
        "from_imports": {k: dict(v) for k, v in from_imports.items()},
        "from_import_files": {k: sorted(v) for k, v in from_import_files.items()},
        "attr_uses": {k: dict(v) for k, v in attr_uses.items()},
        "attr_use_files": {k: sorted(v) for k, v in attr_use_files.items()},
        "module_importers": {k: sorted(v) for k, v in module_importers.items()},
        "patch_sites": patch_sites, "source_pins": source_pins, "file_pins": file_pins,
        "star_imports": star_imports,
    }


def report(a: dict) -> str:
    out = []
    w = out.append
    syms = a["symbols"]
    defs = [s for s in syms if s["kind"] in ("def", "class")]
    consts = [s for s in syms if s["kind"] == "const"]
    muts = [s for s in syms if s["kind"] == "MUTABLE"]
    w(f"# Anatomy of `{a['path']}` ({a['module']})")
    w("")
    w(f"{a['lines']} lines · {len(defs)} top-level defs/classes · {len(consts)} constants · "
      f"{len(muts)} MUTABLE module-level values · {len(a['module_imports'])} module-level imports · "
      f"{len(a['deferred_imports'])} deferred (function-local) imports")
    w("")
    w("## Section markers")
    for ln, text in a["markers"]:
        w(f"- {ln}: {text}")
    if not a["markers"]:
        w("- (none)")
    w("")
    w("## Module-level MUTABLE state and `global` writers")
    for s in muts:
        writers = a["global_writers"].get(s["name"], [])
        w(f"- {s['start']}: `{s['name']}`" + (f" — rebound by `global` in: {', '.join(writers)}" if writers else ""))
    for name, writers in a["global_writers"].items():
        if name not in {s["name"] for s in muts}:
            w(f"- `{name}` rebound by `global` in: {', '.join(writers)} (not a mutable literal)")
    if not muts and not a["global_writers"]:
        w("- (none)")
    w("")
    w("## Top-level symbols in file order (start-end, lines) and intra-module refs")
    for s in syms:
        r = a["refs"].get(s["name"])
        refstr = f" → refs: {', '.join(r)}" if r else ""
        w(f"- {s['start']}-{s['end']} ({s['lines']}) {s['kind']} `{s['name']}`{refstr}")
    w("")
    w("## Connected components of the def/class reference graph (size ≥ 2)")
    for comp in a["components"]:
        if len(comp) >= 2:
            w(f"- [{len(comp)}] " + ", ".join(comp))
    singles = [c[0] for c in a["components"] if len(c) == 1]
    w(f"- singletons ({len(singles)}): " + ", ".join(singles))
    w("")
    w("## Deferred imports (line, inside, module, names)")
    for ln, fn, mod, names in a["deferred_imports"]:
        w(f"- {ln} in `{fn}`: {mod} {names if names else ''}")
    if not a["deferred_imports"]:
        w("- (none)")
    w("")
    w("## External contract")
    mi = a["module_importers"]
    w(f"- files importing the MODULE OBJECT: {len(mi['prod'])} prod, {len(mi['test'])} test")
    if a["star_imports"]:
        w(f"- STAR IMPORTS of this module: {a['star_imports']}")
    w("")
    w("### `from <module> import <name>` — name: prod/test file-count")
    for name, c in sorted(a["from_imports"].items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        defined = "" if name in {s["name"] for s in syms} or name in {i[3] or i[2].split('.')[0] for i in a["module_imports"]} else "  **(NOT DEFINED HERE — re-export or missing)**"
        w(f"- `{name}`: {c.get('prod', 0)}/{c.get('test', 0)}{defined}")
    w("")
    w("### attribute uses through the module object — attr: prod/test use-count")
    for name, c in sorted(a["attr_uses"].items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        defined = "" if name in {s["name"] for s in syms} or name in {i[3] or i[2].split('.')[0] for i in a["module_imports"]} else "  **(NOT DEFINED HERE)**"
        w(f"- `{name}`: {c.get('prod', 0)}/{c.get('test', 0)}{defined}")
    w("")
    w(f"### monkeypatch / patch sites aimed at this module ({len(a['patch_sites'])})")
    by_name = defaultdict(list)
    for f, ln, name, form in a["patch_sites"]:
        by_name[name].append(f"{f}:{ln}" + ("" if form == "attr" else f" [{form}]"))
    for name, sites in sorted(by_name.items(), key=lambda kv: -len(kv[1])):
        w(f"- `{name}` ({len(sites)}): " + "; ".join(sites[:12]) + (" …" if len(sites) > 12 else ""))
    w("")
    w(f"### source-text pins on the module object ({len(a['source_pins'])})")
    for f, ln, t in a["source_pins"]:
        w(f"- {f}:{ln} {t}")
    w("")
    w(f"### file pins ({len(a['file_pins'])})")
    for f, ln, t in a["file_pins"]:
        w(f"- {f}:{ln} {t}")
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    json_out = None
    if "--json" in args:
        i = args.index("--json")
        json_out = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    out_dir = json_out  # with several paths, --json names a DIRECTORY
    for arg in args:
        path = Path(arg)
        if not path.is_absolute():
            path = ROOT / path
        a = anatomy(path)
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / (path.stem + ".json")).write_text(json.dumps(a, indent=1, default=list), encoding="utf-8")
            (out_dir / (path.stem + ".md")).write_text(report(a), encoding="utf-8")
            print(f"wrote {out_dir / (path.stem + '.md')}  ({a['lines']} lines, {len(a['symbols'])} symbols)")
        else:
            print(report(a))
