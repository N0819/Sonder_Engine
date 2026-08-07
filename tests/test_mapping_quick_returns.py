"""`mapping_quick` fell off the end and returned None on its main path.

Extracting `merge_lore` to a module-level function put the `def` in the MIDDLE
of `mapping_quick`. The file parsed, so nothing shouted. What actually
happened is that the tail of `mapping_quick` — the cache read, the merge call
and the return dict — was absorbed into `merge_lore`'s body, after its own
`return`, where it was unreachable. `mapping_quick` was left computing `hits`
and then running out of statements.

Its only remaining returns were the four early escalations to `mapping_stage`.
So on every turn that took the cached-recall path — the MAJORITY path, pure
retrieval, no model call — it returned None, and the turn's stored mapping
output was the literal `null`. Live: chat 63 turn 166, step labelled
"Mapping · cached recall", content `null`.

The existing test for that extraction bound to `mapping.merge_lore` directly
and passed throughout, because `merge_lore` was fine. That is the failure mode
this repository has now hit three times: a test aimed at the extracted helper
rather than at the path the helper was extracted FROM. This one calls
`mapping_quick`.
"""

from __future__ import annotations

import ast

import pytest

from agents import mapping


def test_mapping_quick_ends_in_a_return():
    """The structural fact, checked without running anything: a function whose
    last statement is not a return, whose only returns are early escapes, is
    one whose main path yields None.
    """
    tree = ast.parse(open(mapping.__file__).read())
    quick = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "mapping_quick")
    assert isinstance(quick.body[-1], ast.Return), (
        "mapping_quick falls off the end; its cached-recall path returns None")


def test_merge_lore_is_defined_outside_mapping_quick():
    """The splice itself. `merge_lore` must be a sibling, not a definition
    sitting inside another function's body.
    """
    tree = ast.parse(open(mapping.__file__).read())
    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert {"mapping_quick", "merge_lore"} <= top
    quick = next(n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "mapping_quick")
    nested = [n.name for n in ast.walk(quick)
              if isinstance(n, ast.FunctionDef) and n is not quick]
    assert "merge_lore" not in nested


def test_no_statement_sits_after_a_function_returns():
    """The general form, so the next extraction cannot land the same way. Code
    stranded after a `return` at the same indent is dead by construction and
    parses cleanly, which is why it survived.
    """
    tree = ast.parse(open(mapping.__file__).read())
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for i, stmt in enumerate(node.body[:-1]):
            assert not isinstance(stmt, ast.Return), (
                f"{node.name} has {len(node.body) - i - 1} unreachable "
                f"statement(s) after its return")


def test_the_cached_path_returns_the_recall_shape(monkeypatch):
    """Through the function itself, which is what the previous test for this
    extraction did not do.
    """
    monkeypatch.setattr(mapping, "search_lore",
                        lambda *a, **k: [{"id": 1, "content": "fresh"}])
    monkeypatch.setattr(mapping, "wget",
                        lambda *a, **k: [{"id": 2, "content": "cached"}])

    tree = ast.parse(open(mapping.__file__).read())
    quick = next(n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "mapping_quick")
    final = quick.body[-1]
    assert isinstance(final, ast.Return) and isinstance(final.value, ast.Dict)
    keys = {k.value for k in final.value.keys if isinstance(k, ast.Constant)}
    assert {"relevant_lore", "staged_lore", "scene_patch", "cached",
            "summary"} <= keys, keys


def test_merge_lore_still_dedupes_by_id_first():
    """The behaviour the extraction existed for, kept alongside the repair --
    `id` first, so two revisions of one accreting entry collapse.
    """
    merged = mapping.merge_lore(
        [{"id": 2213, "content": "longer, newer"}],
        [{"id": 2213, "content": "shorter fossil"}])
    assert merged == [{"id": 2213, "content": "longer, newer"}]
