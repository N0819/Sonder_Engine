"""`static/js/` is one namespace, and load order silently decides who wins.

The files are browser globals, not ES modules, so a top-level `function foo`
in one file and a `window.foo = bar` in another are the SAME binding -- the
later script simply wins, with no error anywhere. `node --check` cannot see it
(a redefinition is legal), the browser console says nothing, and the losing
definition stays maintained-looking code that a reader will edit expecting an
effect.

Measured: `editors.js` carried a complete 75-line `loreModal` lorebook editor
that `lorebooks.js:636`'s `window.loreModal = openLoreWorkspace` had been
overwriting since the workspace was built. Every call site in four files
reached the workspace; nobody could have known from reading `editors.js`.

These are the two collisions that shape can take. Both are clean today, which
is the point of pinning them: the failure is invisible until somebody looks.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_DIR = ROOT / "static" / "js"
INDEX = ROOT / "static" / "index.html"

# A declaration at column 0 is a top-level one, which in a classic script means
# a global. Indented matches are inside some function and cannot collide.
_DECLARED = re.compile(
    r"^(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
_WINDOW_WRITE = re.compile(r"^\s*window\.([A-Za-z_$][\w$]*)\s*=", re.MULTILINE)


def _loaded_files() -> list[Path]:
    """The files index.html actually loads, in load order."""
    html = INDEX.read_text(encoding="utf-8")
    names = re.findall(r'src="/static/js/([\w.-]+\.js)"', html)
    assert names, "no frontend scripts found in index.html"
    return [JS_DIR / name for name in names]


def _declarations() -> dict[str, str]:
    """Global name -> the file that declares it."""
    owners: dict[str, str] = {}
    for path in _loaded_files():
        for name in _DECLARED.findall(path.read_text(encoding="utf-8")):
            owners.setdefault(name, path.name)
    return owners


def test_no_global_is_declared_at_top_level_in_two_files():
    """The silent case: two files declaring one name. Whichever loads last
    wins, and the other body becomes unreachable without saying so."""
    seen: dict[str, str] = {}
    collisions = []
    for path in _loaded_files():
        for name in set(_DECLARED.findall(path.read_text(encoding="utf-8"))):
            if name in seen and seen[name] != path.name:
                collisions.append(f"{name}: {seen[name]} and {path.name}")
            seen.setdefault(name, path.name)
    assert not collisions, "top-level declarations collide across files: " + \
        "; ".join(sorted(collisions))


def test_no_file_overwrites_a_global_another_file_declares():
    """The `loreModal` case: a `window.X =` in one file silently replacing a
    declaration in another. A same-file re-export is fine and common -- it is
    the CROSS-file write that kills a body nobody can see is dead."""
    owners = _declarations()
    overwrites = []
    for path in _loaded_files():
        for name in set(_WINDOW_WRITE.findall(path.read_text(encoding="utf-8"))):
            owner = owners.get(name)
            if owner and owner != path.name:
                overwrites.append(f"window.{name} in {path.name} overwrites "
                                  f"the declaration in {owner}")
    assert not overwrites, "; ".join(sorted(overwrites))


# The host's own entry points, as opposed to an optional module. These are
# reached FORWARD as bare identifiers from four files, deliberately unguarded:
# guarding one would turn a missing core script from a loud throw (which the
# error net in app.js toasts) into a click that silently does nothing.
HOST_ENTRY_POINTS = ("boot", "renderSide", "openChat", "newChatWizard")


def test_no_file_calls_a_host_entry_point_at_load_time():
    """A forward reference is safe when it is DEFERRED -- it resolves when the
    click happens, by which time every script on the page has run. What is not
    safe is calling one at top level from a file that loads earlier, which
    would run before the definition exists. That is the actual hazard in a
    single namespace ordered by <script> tags, and the guard `typeof` offers is
    not a substitute for it.
    """
    offenders = []
    for path in _loaded_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line or line[:1].isspace() or line.lstrip().startswith("//"):
                continue
            for name in HOST_ENTRY_POINTS:
                if re.match(r"^(await\s+)?%s\s*\(" % name, line.strip()):
                    if path.name == "app.js" and name == "boot":
                        continue  # its own file, after its own definition
                    offenders.append(f"{path.name}:{number} {line.strip()[:60]}")
    assert not offenders, "; ".join(offenders)
