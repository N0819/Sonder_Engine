"""The splitting tools find their checkout from where they sit, and the
splitter runs the gate's OWN facade rules, not a paraphrase of them.

`tools/split_module.py` and `tools/module_anatomy.py` applied the
`agents/common.py`, `agents/composer.py` and `agents/perception.py` splits on
2026-11-01 from a scratch directory, with the checkout's path written into
them. Here they derive it from their own location. And the splitter compiles a
named subset of `tools/project_check.py` (`PC_PURE`, `PC_DISK`) instead of
importing it, so a helper the gate's functions grow is one the subset must
carry too -- or the splitter's facade checks die mid-split with a NameError,
or are skipped with a warning nobody reads.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    """The tool as its own module object -- registered while it executes,
    because its dataclasses resolve their annotations through it."""
    import sys

    spec = importlib.util.spec_from_file_location(
        "split_tool_" + name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_both_tools_find_the_checkout_they_sit_in():
    anatomy = _load("module_anatomy")
    splitter = _load("split_module")
    assert anatomy.ROOT == ROOT
    assert splitter.DEFAULT_ROOT == ROOT
    assert Path(splitter.DEFAULT_PYTHON).exists()


def test_the_splitter_compiles_every_helper_the_gate_rules_call(tmp_path):
    splitter = _load("split_module")
    diag = splitter.Diag()
    ns = splitter.load_project_check(ROOT, diag)
    assert not diag.warnings, diag.warnings

    hits = ns["facade_import_violations"](
        "from .director_floors import x\n", pkg="agents", stem="director",
        siblings={"director_floors"}, module="agents.character")
    assert [kind for _line, kind, _target in hits] == ["outside-in"]
    assert ns["facade_patch_sites"](
        ast.parse("monkeypatch.setattr('persist.commit.x', None)\n")) == [
        (1, "persist.commit", "x")]

    # PC_DISK as `run_disk_checks` runs them: against a family on disk.
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "fac.py").write_text("from .fac_low import helper\n",
                                encoding="utf-8")
    (pkg / "fac_low.py").write_text("def helper():\n    return 1\n",
                                    encoding="utf-8")
    (pkg / "caller.py").write_text("from .fac_low import helper\n",
                                   encoding="utf-8")
    (tmp_path / "tests").mkdir()
    ns["ROOT"] = tmp_path
    ns["FACADE_FAMILIES"] = {"pkg.fac": (pkg, "fac")}
    ns["engine_python_paths"] = lambda: sorted(pkg.glob("*.py"))
    errors: list[str] = []
    ns["check_facade_import_direction"](errors)
    assert [error.split(":")[0] for error in errors] == ["pkg/caller.py"]
    errors = []
    ns["check_facade_patch_targets"](errors)
    assert errors == []
