"""What `tools/project_check.py`'s matchers actually match.

A structure check is only worth its runtime if it fires. These are the cases a
matcher must get right, written against the matcher itself rather than against
the repository, so a rule can be proved to have teeth without waiting for
somebody to break the tree.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from project_check import facade_import_violations  # noqa: E402


FAMILY = dict(pkg="persist", stem="commit",
              siblings={"commit_memory", "commit_memory_write"})


def _kinds(source, **kw):
    return [kind for _, kind, _ in facade_import_violations(source, **FAMILY, **kw)]


def test_engine_sibling_import_flagged_in_both_spellings():
    """`from persist import commit_memory_write` is the spelling in use.

    The matcher `rpartition`ed the module name, so this form yielded the tail
    `"persist"` -- never a sibling, never reported. Every sibling import in the
    tree is written this way, so the rule held only where nobody was writing.
    """
    assert _kinds("from persist.commit_memory import prepare\n") == ["outside-in"]
    assert _kinds("from persist import commit_memory_write\n") == ["outside-in"]
    assert _kinds("import persist.commit_memory\n") == ["outside-in"]
    assert _kinds("from persist import commit\n") == []


def test_sibling_importing_its_own_facade_flagged_in_both_spellings():
    inside = dict(inside=True)
    assert _kinds("from persist import commit\n", **inside) == ["inside-out"]
    assert _kinds("import persist.commit\n", **inside) == ["inside-out"]


def test_a_test_may_name_the_sibling_it_patches():
    """The split's own correctness requirement, and the check must permit it.

    A monkeypatch must name the module that DEFINES the function it intercepts
    -- a moved function resolves names in its own globals, so a patch on the
    facade's re-export is silently inert (docs/experiments/AUDIT_COMMIT.md).
    The facade rule is about callers; a patch target is not a call.
    """
    src = (
        "from persist import commit_memory_write\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(commit_memory_write, 'add_memories_batch', None)\n"
    )
    assert _kinds(src, is_test=True) == []


def test_a_test_may_name_the_sibling_whose_source_it_reads():
    src = (
        "from persist import commit_memory\n"
        "def test_x():\n"
        "    open(commit_memory.__file__).read()\n"
    )
    assert _kinds(src, is_test=True) == []


def test_a_test_that_only_calls_through_the_sibling_is_still_flagged():
    """The exemption is for the module object, not for convenience."""
    src = (
        "from persist import commit_memory\n"
        "def test_x():\n"
        "    commit_memory.prepare_memories_batch([])\n"
    )
    assert _kinds(src, is_test=True) == ["outside-in"]
    assert _kinds(src) == ["outside-in"]


def test_pre_move_module_names_are_reported_with_where_they_went():
    """`tools/` is imported by nothing, so a stale name fails only on use.

    `tools/perception_quality.py` asked for `spatial` and `character_schema`
    for weeks after they became `world.spatial` and `story.character_schema`;
    both landed in a bare `except`, its entitlement gate was off for every
    view, and it exited 0.
    """
    from project_check import (_engine_module_index, engine_import_violations)

    names, by_tail = _engine_module_index()
    assert "world.spatial" in names

    hits = engine_import_violations("import spatial\n", names, by_tail)
    assert [m for _, m in hits] == [
        "imports 'spatial', a module name from before the package move. "
        "It is now world.spatial."]

    hits = engine_import_violations("from world.gone import x\n", names, by_tail)
    assert [m for _, m in hits] == [
        "imports 'world.gone', which is not a module in this tree."]

    assert engine_import_violations(
        "from world.spatial import room_of\nimport json\n", names, by_tail) == []


def test_facade_siblings_are_read_off_the_facade_not_the_filenames():
    """A filename prefix is a guess about membership, and here it is wrong.

    `world/spatial_frames.py` matches `spatial_*` and is not behind
    `world/spatial.py` — the facade has zero references to it — so a family
    built by prefix would flag correct imports of it as facade violations.
    """
    from project_check import ROOT, facade_siblings

    spatial = facade_siblings(ROOT / "world", "spatial")
    assert "spatial_orientation" in spatial
    assert "spatial_frames" not in spatial

    # Relative spelling: agents/director.py imports `from .director_lingua`.
    director = facade_siblings(ROOT / "agents", "director")
    assert "director_lingua" in director and "director_scopes" in director

    commit = facade_siblings(ROOT / "persist", "commit")
    assert "commit_memory_write" in commit
