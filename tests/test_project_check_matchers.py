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
