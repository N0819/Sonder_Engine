"""Language-pack access for the Director family.

The pack key is the string literal "agents.director" -- a language-pack
coordinate, not a module identity: `tools/build_japanese_pack.py` and
`tests/test_language_packs.py` key on it. Do not rewrite it to `__name__`
or to this module's name.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

from language_runtime import linguistic


def _ling(name):
    """One cue, in the story's own language.

    THE ONLY WAY THE DIRECTOR READS A CUE. Three of them used to also exist as
    module constants bound eagerly through `english_linguistic` at import --
    labelled "English compatibility views" and read by no runtime path, alive
    only as test fixtures. So the tests guarding the awareness vocabulary were
    pinned to English without saying so, and would not have fired on a story
    in any other language: exactly the failure they were written to prevent.
    The English objects are still reachable by name for a test that wants
    them, and `tests/test_language_packs.py` guards the Japanese ones with
    Japanese fixtures, which is the only way that can be done.
    """
    return linguistic("agents.director", name)
