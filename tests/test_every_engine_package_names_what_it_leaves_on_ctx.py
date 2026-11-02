"""A value left on the turn's context is a field or a declared side channel,
whichever package leaves it.

`tools/project_check.py`'s side-channel guard walked `agents/` and `story/`
only. `extension_runtime` writes `ctx["_extension_routing"]` -- the record of
which extension rewrote what a mind was given, read back at commit so a mind
that knows something it should not is traced to its author -- and no register
named it (audit of 2026-11-01, tooling_gate F3). `setattr(ctx, KEY, value)`
was a write form the walker could not read either:
`persist/commit_common.mark_engine_notices_rewritten` stamps one.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402


def _keys(source):
    tree = ast.parse(source)
    constants = pc._module_string_constants(tree)
    return sorted(key for node in ast.walk(tree)
                  for key in pc._pipeline_context_channel_writes(node,
                                                                 constants))


def test_every_engine_package_is_walked():
    assert set(pc.ENGINE_PACKAGE_ROOTS) <= set(pc._SIDE_CHANNEL_ROOTS)


def test_a_setattr_on_the_context_is_a_write():
    assert _keys("def f(ctx):\n    setattr(ctx, '_stamp', True)\n") == [
        "_stamp"]
    assert _keys('KEY = "_stamp"\n'
                 "def f(ctx):\n    setattr(ctx, KEY, True)\n") == ["_stamp"]
    # A setattr on something else is not a write to the turn's context.
    assert _keys("def f(other):\n    setattr(other, '_stamp', True)\n") == []


def test_the_extension_routing_record_is_declared_with_how_it_survives():
    from agents import runtime

    assert "_extension_routing" in runtime.SIDE_CHANNELS
    assert "_engine_notices_rewritten" in runtime.SIDE_CHANNELS
