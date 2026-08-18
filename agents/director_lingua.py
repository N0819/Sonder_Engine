"""Language-pack access for the Director family.

The pack key is the string literal "agents.director" -- a language-pack
coordinate, not a module identity: `tools/build_japanese_pack.py` and
`tests/test_language_packs.py` key on it. Do not rewrite it to `__name__`
or to this module's name.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

from language_runtime import english_linguistic, linguistic

def _ling(name):
    return linguistic("agents.director", name)

# English compatibility views only; runtime uses context-local `_ling(...)`.
_UNCONSCIOUSNESS_CUE = english_linguistic(
    "agents.director", "_UNCONSCIOUSNESS_CUE")
_SLEEP_CUE = english_linguistic("agents.director", "_SLEEP_CUE")
_STAY_UNDER_CUE = english_linguistic("agents.director", "_STAY_UNDER_CUE")
