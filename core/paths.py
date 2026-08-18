"""Where the install lives on disk.

ONE statement of the install root. Every module that needs it derives it from
`__file__`, and on 2026-08-18 eighty-one modules moved from the repository
root into packages -- so every one of those derivations silently began naming
its own package directory instead. Three did:

* `core/updates.py`'s `REPO_ROOT` became `<install>/core`, so `_is_git_repo`
  compared the checkout's top level against it, returned False for every real
  install, and both update routes answered "This install is not a git
  checkout" unconditionally. All nine of its tests monkeypatch either that
  constant or the function, so the suite stayed green.
* `dressing/backdrops.py` and `dressing/ambience.py` began looking for the
  host's generated images and fetched audio under `dressing/`. Measured on the
  owner's install at the time of the fix: 47 backdrops (309 MB) and 36
  ambience beds (442 MB) sitting at the install root, invisible to the code
  that wrote them -- so every backdrop would have been re-generated at cost
  and every bed re-fetched.

`extension_runtime` and `language_runtime` had it right, by counting one
`.parent` more than the others. That is the whole difference between the two
groups, which is why this is a constant rather than a convention.

`tools/project_check.py` refuses a new install-root derivation outside this
module.
"""

import os

#: The directory the engine is installed in: the one holding `Makefile`,
#: `engine.db`, `static/`, `language_packs/`, and the subsystem packages.
INSTALL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
