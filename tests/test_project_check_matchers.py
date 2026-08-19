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


def test_every_facade_family_is_checked():
    """`world.spatial` was the third facade of this shape and sat outside the
    check for as long as the check existed, behind a comment saying adding the
    line was all it took. It took the line plus eight import sites -- one in
    `world/crowds.py` and seven in tests -- each of which is the drift a facade
    rule exists to stop: a caller that knows which sibling defines a name, and
    therefore pins where the name lives.

    `mind.memory` is the fourth (2026-08-19, `docs/design/SPLIT_MEMORY.md`) and
    cost the same shape of debt on registration: seven monkeypatches across
    four test files aimed at a facade name whose reader had moved. Not one of
    them had failed -- they stub an embedding provider, and an uninstalled stub
    falls back silently -- so this check is what found them.

    The set is asserted whole, and deliberately. A family that is split but not
    registered is invisible exactly the way `world.spatial` was.
    """
    from project_check import FACADE_FAMILIES, facade_siblings

    assert set(FACADE_FAMILIES) == {
        "agents.director", "commit", "mind.memory", "world.spatial"}
    for facade, (home, stem) in FACADE_FAMILIES.items():
        assert facade_siblings(home, stem), facade


# ---- cross-file duplicate definitions (STORY-F11) --------------------------


def _duplicate_bodies(sources):
    """Run the cross-file rule over a fake tree of `{relative path: source}`."""
    import ast

    import project_check

    seen = {}
    for rel, source in sorted(sources.items()):
        tree = ast.parse(source)
        for name, body in project_check._module_level_bodies(tree, source).items():
            if name in project_check._PER_MODULE_HOOKS:
                continue
            if len(body.splitlines()) < project_check._DUPLICATE_MIN_LINES:
                continue
            seen.setdefault((name, body), []).append(rel)
    return {name for (name, _), files in seen.items() if len(files) > 1}


SANITIZE = '''def sanitize_attire_items(items):
    result = []
    for item in items or []:
        if item:
            result.append(item)
    return result
'''


def test_one_definition_copied_into_two_modules_is_reported():
    """The per-file check resolves a redefinition by discarding the first.

    Python resolves this one by keeping BOTH, which is why it needs its own
    rule: `sanitize_attire_items` lived in three modules with separate
    consumers, and neither file was wrong on its own.
    """
    assert _duplicate_bodies({
        "story/attire.py": SANITIZE,
        "story/scene.py": SANITIZE,
    }) == {"sanitize_attire_items"}


def test_the_same_name_with_a_different_body_is_not_a_copy():
    """Name alone would make this noise: every package has a `_normalize`."""
    other = SANITIZE.replace("result.append(item)", "result.append(str(item))")
    assert _duplicate_bodies({
        "story/attire.py": SANITIZE,
        "world/crowds.py": other,
    }) == set()


def test_a_module_hook_is_exempt_because_it_cannot_be_shared():
    """A module-level `__getattr__` is resolved per module: defining one in
    each module that needs it is the only way to have one at all, so "import
    it instead" is advice that cannot be followed."""
    hook = (
        "def __getattr__(name):\n"
        "    pid = _COMPAT.get(name)\n"
        "    if pid is None:\n"
        "        raise AttributeError(name)\n"
        "    return pid\n"
    )
    assert _duplicate_bodies({
        "story/importers.py": hook,
        "world/offscreen.py": hook,
    }) == set()


def test_the_repo_has_no_cross_file_duplicates():
    from project_check import check_cross_file_duplicate_definitions

    errors: list[str] = []
    check_cross_file_duplicate_definitions(errors)
    assert errors == [], errors
