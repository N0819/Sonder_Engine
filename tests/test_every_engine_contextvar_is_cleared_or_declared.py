"""A contextvar anywhere in the engine is cleared for a background job, or
declared safe with a reason -- and is reset between tests.

`core/jobs.py::submit` hands a job a copy of the commit step's whole context,
and `_clear_turn_scoped_context` takes the turn's own things back out. The
structural check that holds that denylist to the source read two modules,
`llm/providers.py` and `core/pipeline_context.py`, while seven contextvars
lived in seven others (2026-11-01) -- four of them added after the audit the
denylist's docstring cites, among them a Room reply's mutable citation set and
a commit's private registry copy. The per-test reset in `tests/conftest.py`
had the same blind spot: `llm.providers` only.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402

JOBS = ("def _clear_turn_scoped_context():\n"
        "    from llm.providers import token_sink\n"
        "    for var in (token_sink,):\n"
        "        var.set(None)\n")


def _tree(tmp_path, monkeypatch, files):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "jobs.py").write_text(JOBS, encoding="utf-8")
    paths = []
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    monkeypatch.setattr(pc, "ROOT", tmp_path)
    monkeypatch.setattr(pc, "engine_python_paths", lambda: sorted(paths))
    errors: list[str] = []
    pc.check_turn_scoped_contextvars_are_cleared(errors)
    return errors


def test_a_contextvar_outside_the_two_old_modules_is_held_too(tmp_path,
                                                               monkeypatch):
    errors = _tree(tmp_path, monkeypatch, {
        "story/elsewhere.py":
            "import contextvars\n"
            "_reply_rows = contextvars.ContextVar('rows', default=None)\n"})
    assert any("story/elsewhere.py" in error and "'_reply_rows'" in error
               for error in errors), errors


def test_a_cleared_or_declared_contextvar_passes(tmp_path, monkeypatch):
    errors = _tree(tmp_path, monkeypatch, {
        "llm/providers.py":
            "import contextvars\n"
            "token_sink = contextvars.ContextVar('token_sink', default=None)\n",
        "language_runtime/__init__.py":
            "import contextvars\n"
            "current_language_id = contextvars.ContextVar('l', default='en')\n"})
    assert errors == []


def test_one_name_in_two_modules_is_reported(tmp_path, monkeypatch):
    """The safe list keys on the name, so one reason must not cover two
    different vars that happen to share it."""
    errors = _tree(tmp_path, monkeypatch, {
        "story/a.py": "import contextvars\n"
                      "current_language_id = contextvars.ContextVar('a')\n",
        "world/b.py": "import contextvars\n"
                      "current_language_id = contextvars.ContextVar('b')\n"})
    assert any("defined in 2 modules" in error for error in errors), errors


def test_the_per_test_reset_reaches_every_engine_contextvar():
    import language_runtime
    from core import db
    from llm import providers
    from story import room_citations
    from tests.helpers import engine_contextvars

    found = engine_contextvars()
    for var in (db.active_frame_id, language_runtime.current_language_id,
                room_citations._rows_read, providers.token_sink):
        assert any(held is var for held in found), var.name
    assert len({id(var) for var in found}) == len(found)
