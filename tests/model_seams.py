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

The doors are `tests/helpers.py`'s `MODEL_DOORS`, the ONE list: this file kept
a second one, and the two disagreed (three doors there, five here, neither
naming the decision model's post that arrived after both). A caller that bound
a door at import time holds its own reference, so every engine module holding
the SAME function object is sealed too; identity is the test, never the name,
or an unrelated module with a same-named attribute would be patched as well.

Adding a provider entry point means adding it to `MODEL_DOORS`, and
`tests/test_model_seams.py` proves each door is really shut by opening it. A
door the list forgets is no longer a path to the network: `tests/conftest.py`
refuses any connection off this machine whatever door opened it -- the list is
what names the door.
"""

from __future__ import annotations

import pytest

from tests.helpers import MODEL_DOORS, seal_doors

__all__ = ("MODEL_DOORS", "seal_model_seams", "sealed_model")


def seal_model_seams(monkeypatch, *, doors=MODEL_DOORS):
    """Make every model door raise. Returns the names of the doors sealed."""

    def refusal_for(door):
        def refuse(*args, **kwargs):
            raise AssertionError(f"a model was reached through {door}")
        return refuse

    _bindings, sealed = seal_doors(monkeypatch.setattr, refusal_for, doors)
    assert sealed, "no model door was found to seal"
    return sealed


@pytest.fixture
def sealed_model(monkeypatch):
    """Fixture form: any model call inside the test fails the test."""
    return seal_model_seams(monkeypatch)
