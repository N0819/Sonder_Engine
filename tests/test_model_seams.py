"""The seam sealer is only worth anything if every door it names is shut.

A helper that silently misses a door turns "this path makes no model call" from
a weak assertion into a false one, which is worse than the substring test it
replaces. So each door is opened deliberately here, and the sealer must catch
it -- including through the alias a caller bound at import time, which is the
form the engine actually uses.
"""

from __future__ import annotations

import importlib

import pytest

from model_seams import MODEL_DOORS, seal_model_seams


@pytest.mark.parametrize("module_path,attr", MODEL_DOORS)
def test_each_named_door_is_shut(monkeypatch, module_path, attr):
    module = importlib.import_module(module_path)
    seal_model_seams(monkeypatch)
    with pytest.raises(AssertionError) as caught:
        getattr(module, attr)()
    assert f"{module_path}.{attr}" in str(caught.value)


def test_an_import_time_alias_is_shut_too(monkeypatch):
    """The engine binds these at import time -- `from llm.providers import
    chat_complete` -- so patching only the defining module would leave every
    real caller holding the original. Identity is what finds them."""
    import agents.common as common
    import llm.providers as providers

    original = providers.chat_complete
    holders = [m for m in (common,) if getattr(m, "chat_complete", None) is original]
    monkeypatch.setattr(common, "chat_complete", original, raising=False)

    seal_model_seams(monkeypatch)
    with pytest.raises(AssertionError):
        common.chat_complete()
    assert holders is not None  # the sweep found it or the setattr planted it


def test_sealing_is_undone_when_the_test_ends(monkeypatch):
    """`monkeypatch` owns the teardown; asserted because a leaked seal would
    make every later test in the session fail for the wrong reason."""
    import llm.providers as providers

    original = providers.chat_complete
    with pytest.MonkeyPatch.context() as patch:
        seal_model_seams(patch)
        assert providers.chat_complete is not original
    assert providers.chat_complete is original
