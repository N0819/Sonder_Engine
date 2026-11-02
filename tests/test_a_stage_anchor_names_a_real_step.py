"""A stage's anchor names a step some plan actually runs, or it is refused
where the extension can read why.

Audit 2026-11-01 (web_routes_extensions F15, CONFIRMED by snippet):
`api.add_stage("tally", anchor="after:director_resolv")` and
`anchor="after:mapping"` (a stage retired 2026-09) both registered -- handler
present, `registered_stages()` listing them -- and were never planned on any
turn, with nothing anywhere saying so. That is the exact silence the
reserved-prefix refusal beside it was written to end ("used to register
cleanly, appear in registered_stages(), and never run on any turn"). The core
step keys are a closed set the engine owns: `agents.runtime.STEP_HANDLERS`.
"""

from __future__ import annotations

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _enable, _write_extension, ext_root,
)


@pytest.fixture
def api(ext_root):
    _write_extension(ext_root, "anchored", {
        "id": "anchored", "version": "1.0.0", "ext_api": 1, "name": "Anchored",
        "capabilities": {"python": "extension.py"},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("anchored")
    return extension_runtime._apis["anchored"]


@pytest.mark.parametrize("anchor", ["after:director_resolv", "after:mapping",
                                    "before:narrator.establish"])
def test_an_anchor_naming_no_step_is_refused_naming_the_steps(api, anchor):
    with pytest.raises(ExtensionError) as excinfo:
        api.add_stage("tally", anchor=anchor, handler=lambda v, a, n: {})

    message = str(excinfo.value)
    assert "director_resolve" in message and "narrator" in message
    assert extension_runtime.registered_stages() == []


@pytest.mark.parametrize("anchor", ["after:director_resolve", "before:narrator",
                                    "after:skip_lives", "before:commit",
                                    "after:director_establish"])
def test_every_core_step_is_a_valid_anchor(api, anchor):
    assert api.add_stage("tally", anchor=anchor,
                         handler=lambda v, a, n: {}) == "ext:anchored:tally"


def test_a_misspelt_anchor_disables_the_extension_with_the_reason(ext_root):
    _write_extension(ext_root, "typo", {
        "id": "typo", "version": "1.0.0", "ext_api": 1, "name": "Typo",
        "capabilities": {"python": "extension.py"},
    }, {"extension.py":
        "def register(api):\n"
        "    api.add_stage('a', anchor='after:director_resolv',\n"
        "                  handler=lambda v, x, n: {})\n"})
    _enable("typo")

    assert "director_resolv" in extension_runtime.disabled_reasons()["typo"]
