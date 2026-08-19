"""Two localizers, one set of rules.

`static/js/utils.js` localizes the host SPA; `static/js/i18n.js` localizes the
login and guest pages, which deliberately do not load the SPA. Running both on
one page meant a second catalog fetch, a second permanent observer, and a race
over which localized a node first -- so there are two implementations on
purpose, and `i18n.js`'s own header asks that their RULES stay identical.

They have drifted twice. The first time over whitespace, which ate the space in
`Hinami 何をすべきか決めている`. The second over the skip set: `utils.js` applies
its skip tree to attributes as well as text, after a character named "Cast" got
a translated tooltip on the very element whose text `translate="no"` was
protecting -- and `i18n.js` applied no skip filter to attributes at all.

A shared module would be the real answer, and is not available here: `i18n.js`
must stand alone on a page that loads nothing else. So the equality is pinned
instead.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS = (ROOT / "static/js/utils.js").read_text(encoding="utf-8")
I18N = (ROOT / "static/js/i18n.js").read_text(encoding="utf-8")


def _selector(source: str, name: str) -> str:
    match = re.search(r"\b%s = ('[^']*'|\"[^\"]*\")" % re.escape(name), source)
    assert match, f"{name} not found"
    return match.group(1).strip("'\"")


def test_both_localizers_skip_the_same_subtrees():
    assert _selector(UTILS, "I18N_SKIP_TREE") == _selector(I18N, "SKIP_TREE")


def test_both_localizers_exclude_the_same_editable_content():
    """A textarea or input excludes only its CONTENT -- that content is data
    being edited, while its placeholder and title are still chrome."""
    assert "I18N_SKIP_TEXT = I18N_SKIP_TREE + ',textarea,input'" in UTILS
    assert "SKIP_TEXT = SKIP_TREE + ',textarea,input'" in I18N


def test_both_localizers_apply_the_skip_tree_to_attributes_too():
    """The divergence that was live: a subtree opted out must be opted out for
    both passes, or a `translate="no"` element keeps a translated tooltip."""
    for source, skip in ((UTILS, "I18N_SKIP_TREE"), (I18N, "SKIP_TREE")):
        attr_pass = source[source.index('"[title],[aria-label]'):]
        assert f".filter(element => !element.closest({skip}))" in attr_pass
        assert f"!root.closest({skip})" in attr_pass
