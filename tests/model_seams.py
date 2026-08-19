"""Seal every door a model can be reached through, and drive the code.

"This path makes no model call" was written across the suite as a SUBSTRING
ABSENCE -- `"chat_complete" not in inspect.getsource(fn)` -- and that assertion
holds for any spelling that avoids the two words it names. An aliased import, a
call through `llm.llm_quality.complete_validated_json`, or a provider reached
through a module the file already imports all pass it. Measured on
`story/carriers.py` (`a973cb2`), where the same three-line assertion stood in
for the property while the file grew new imports around it.

It is also read from DISK at assert time, against a module object imported
earlier, so anything editing that file concurrently makes it fail once and pass
on re-run.

So: patch the doors themselves and run the code. A path that opens one raises
from inside the call, naming which door -- which is a better failure than a
missing substring, because it says what WAS called rather than what was not
written.

The doors are the provider surface plus the agent-side wrapper. A caller that
bound the name at import time holds its own reference, so every module holding
the SAME function object is patched too; identity is the test, never the name,
or an unrelated module with a same-named attribute would be patched as well.

Adding a provider entry point means adding it here, and forgetting to is the
one way this can go quiet -- which is why `tests/test_model_seams.py` proves
each door is really shut by opening it.
"""

from __future__ import annotations

import importlib
import sys

import pytest

#: `(defining module, attribute)` for every entry point that reaches a provider.
MODEL_DOORS = (
    ("llm.providers", "chat_complete"),
    ("llm.providers", "embed_texts"),
    ("llm.providers", "embed_texts_meta"),
    ("llm.llm_quality", "complete_validated_json"),
    ("agents.common", "_agent_json"),
)

#: Only engine packages are swept for import-time aliases. A test module or a
#: third-party one holding the same object is not a path the engine can take.
_ENGINE_ROOTS = frozenset(
    {"agents", "world", "story", "mind", "persist", "web", "llm", "core"})


def _aliases(original):
    """Every engine module whose attribute IS `original`."""
    for name, module in list(sys.modules.items()):
        if module is None or name.split(".")[0] not in _ENGINE_ROOTS:
            continue
        for attr, value in list(vars(module).items()):
            if value is original:
                yield module, attr


def seal_model_seams(monkeypatch, *, doors=MODEL_DOORS):
    """Make every model door raise. Returns the names of the doors sealed."""
    sealed = []
    for module_path, attr in doors:
        try:
            module = importlib.import_module(module_path)
        except Exception:
            continue
        original = getattr(module, attr, None)
        if original is None:
            continue
        door = f"{module_path}.{attr}"

        def refuse(*args, _door=door, **kwargs):
            raise AssertionError(f"a model was reached through {_door}")

        for holder, held_as in list(_aliases(original)):
            monkeypatch.setattr(holder, held_as, refuse)
        monkeypatch.setattr(module, attr, refuse)
        sealed.append(door)
    assert sealed, "no model door was found to seal"
    return sealed


@pytest.fixture
def sealed_model(monkeypatch):
    """Fixture form: any model call inside the test fails the test."""
    return seal_model_seams(monkeypatch)
