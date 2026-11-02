"""`patch_seam` refuses a patch that rebound only the module it was named on.

Its docstring promised a raise when it matched nothing -- "a seam matching
nothing is a typo or a rename" -- after a line that always appended the
origin, so the raise could not fire (tooling_gate F9, 2026-11-01). A typo
already raised, as the AttributeError reading the original gives. The case
worth refusing passed in silence: the only binding rebound was the named
module's own, and when that module is a facade, no code reads it.
"""

import sys
import types

import pytest

from tests.helpers import patch_seam


def _module(monkeypatch, name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _defined_outside_the_engine():
    return "real"


def test_a_facade_binding_nobody_else_holds_is_refused(monkeypatch):
    """A facade (an engine module) re-exporting something defined OUTSIDE
    the engine packages: the sweep finds no other holder."""
    _module(monkeypatch, "core._seam_probe_facade",
            helper=_defined_outside_the_engine)
    with pytest.raises(AssertionError, match="found no engine module"):
        patch_seam(monkeypatch, "core._seam_probe_facade", "helper",
                   lambda: "fake")


def test_a_seam_held_by_a_second_module_is_rebound_in_both(monkeypatch):
    def helper():
        return "real"

    facade = _module(monkeypatch, "core._seam_probe_facade", helper=helper)
    reader = _module(monkeypatch, "core._seam_probe_reader", helper=helper)
    patched = patch_seam(monkeypatch, "core._seam_probe_facade", "helper",
                         lambda: "fake")
    assert ("core._seam_probe_reader", "helper") in patched
    assert facade.helper() == reader.helper() == "fake"


def test_a_typo_raises_before_anything_is_patched(monkeypatch):
    _module(monkeypatch, "core._seam_probe_facade")
    with pytest.raises(AttributeError):
        patch_seam(monkeypatch, "core._seam_probe_facade", "missing", None)
