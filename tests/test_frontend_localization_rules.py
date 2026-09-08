"""One translator, loaded twice -- not two translators kept in step by hand.

B25 (review 2026-09-07). `static/js/utils.js` localizes the host SPA;
`static/js/i18n.js` localizes the login and guest pages, which deliberately do
not load the SPA. Running both on one page meant a second catalog fetch, a
second permanent observer, and a race over which localized a node first -- so
the two LOADERS are separate on purpose. What was not on purpose is that the
RULES were copied into both files.

They drifted twice. First over whitespace, which ate the space in
`Hinami 何をすべきか決めている`. Then over the skip set: `utils.js` applies its
skip tree to attributes as well as text, after a character named "Cast" got a
translated tooltip on the very element whose text `translate="no"` was
protecting -- and `i18n.js` applied no skip filter to attributes at all. The
test that used to live here pinned the two copies equal, which catches a
divergence only after it is written.

So the rules moved to `static/js/i18n-core.js`, loaded by the SPA and by the
standalone pages alike, and what is pinned now is that there is exactly one
copy and that every page reads it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
CORE = (STATIC / "js/i18n-core.js").read_text(encoding="utf-8")
UTILS = (STATIC / "js/utils.js").read_text(encoding="utf-8")
I18N = (STATIC / "js/i18n.js").read_text(encoding="utf-8")
ROOM = (STATIC / "js/writers_room.js").read_text(encoding="utf-8")

# Every rule the two localizers once held a copy of apiece.
SHARED_RULES = (
    "I18N_SKIP_TREE",
    "I18N_SKIP_TEXT",
    "I18N_ATTRS",
    "i18nCompileTemplates",
    "i18nTranslate",
    "i18nLocalize",
    "i18nObserve",
)


def test_the_rules_are_defined_once_and_in_the_core():
    for name in SHARED_RULES:
        definitions = [
            source for source in (CORE, UTILS, I18N)
            if re.search(r"^(const|function) %s\b" % re.escape(name),
                         source, re.MULTILINE)
        ]
        assert definitions == [CORE], f"{name} is not defined only in i18n-core.js"


def test_neither_loader_keeps_a_second_walk_of_its_own():
    """The walk is where both divergences happened: the whitespace re-attach
    and the attribute skip filter both live in it."""
    for source in (UTILS, I18N):
        assert "createTreeWalker" not in source
        assert "MutationObserver" not in source


def test_every_page_that_localizes_loads_the_core_first():
    """A page loading a caller without the rules is a ReferenceError on boot,
    which is louder than a divergence but still worth pinning: script order in
    these files is hand-maintained and has no module graph behind it."""
    for page, caller in (("index.html", "utils.js"),
                         ("login.html", "i18n.js"),
                         ("guest.html", "i18n.js")):
        html = (STATIC / page).read_text(encoding="utf-8")
        core_at = html.index("/static/js/i18n-core.js")
        assert core_at < html.index("/static/js/" + caller)


def test_every_harness_that_injects_a_localizer_injects_the_rules_too():
    """The same rule as the page test above, for the other kind of page.

    A page that RUNS a localizer needs the rules on it first, and the served
    HTML is not the only page that runs one: a browser test builds a synthetic
    page out of `static/js` sources and is a loader in exactly the same sense.
    `browser_tests/test_prose_emphasis.py` injects the slice of `utils.js` that
    ends at `t()`, and `t()` stopped being self-contained the moment the rules
    moved out of it -- every test in that file died on
    `ReferenceError: i18nCompileTemplates is not defined` at the first element
    `el()` built, while this Python tier stayed green through it. So the pin is
    on the injection, not on the one file that had the hole.
    """
    localizers = ("utils.js", "i18n.js")
    harnesses = sorted(
        path for directory in ("tests", "browser_tests")
        for path in (ROOT / directory).glob("*.py")
        if "add_script_tag" in path.read_text(encoding="utf-8")
    )
    for path in harnesses:
        source = path.read_text(encoding="utf-8")
        injected = [name for name in localizers if '"%s"' % name in source]
        if not injected:
            continue
        assert '"i18n-core.js"' in source, (
            "%s injects %s without the rules it calls"
            % (path.relative_to(ROOT), ", ".join(injected))
        )


def test_the_spa_still_owns_only_what_is_its_own():
    """Two differences between the pages are real and must stay in the SPA:
    its catalog comes from the bootstrap, and `t()` interpolates `{var}` on
    top of the lookup."""
    body = UTILS[UTILS.index("function t(source, vars = {})"):]
    body = body[:body.index("function watchUILanguage")]

    assert "S.uiCatalog" in body
    assert "out.split(`{${key}}`)" in body


def test_the_writers_room_translates_its_own_lines_and_nothing_else():
    """A74 (review 2026-09-07). `el()` runs a plain string child through `t()`
    before the node is inserted, and the catalog has 349 keys with no space in
    them -- so a Planner sentence, a mandate the player typed, a package title
    or a claim the room stated was looked up as though it were an interface
    label, and a one-word title like "Close" came back translated. The same
    collision `txt()` exists for in the transcript.

    The engine's own lines in this panel are a closed set that is already
    spelled in the file (so the catalog harvests them), so membership decides
    which strings are looked up. `translate="no"` on the element carrying story
    text is the other half: without it the document walk and the mutation
    observer translate the same string a frame later.

    A browser tier would drive it: run the panel under a catalog that maps
    "Close" to something else, post a room message whose whole text is "Close",
    and assert the thread still reads "Close" while the empty-status line is
    translated.
    """
    assert "const ROOM_FIXED_LINES = new Set(" in ROOM
    membership = ROOM[ROOM.index("const ROOM_FIXED_LINES"):]
    membership = membership[:membership.index("// ---- Rendering ----")
                            if "// ---- Rendering ----" in membership else 800]
    for name in ("ROOM_UNSEATED_LINE", "ROOM_NO_STATUS_LINE", "ROOM_PLANNER_LINES"):
        assert name in membership, name

    helper = ROOM[ROOM.index("function roomStoryText(value)"):]
    helper = helper[:helper.index("}\n", helper.index("return"))]
    assert "ROOM_FIXED_LINES.has(line) ? t(line)" in helper
    assert "txt(" in helper

    # Every rendered piece of story text goes through it, under an element that
    # opts out of the walk.
    for field in ('roomStoryText(st && st.line ? st.line : ROOM_NO_STATUS_LINE)',
                  'roomStoryText(item.label + (item.state ? " \u00b7 " + item.state : ""))',
                  "roomStoryText(qn.text)",
                  "roomStoryText(m.text)",
                  "roomStoryText(text)",
                  "roomStoryText(claim.text)",
                  "roomStoryText(live.reasoning)",
                  "roomStoryText(live.text)"):
        assert field in ROOM, field
    for holder in ('class: "room-status-line", translate: "no"',
                   'class: "room-mandate-text", translate: "no"',
                   'class: "room-text", translate: "no"',
                   'class: "room-claim-text", translate: "no"',
                   'class: "room-think", translate: "no"'):
        assert holder in ROOM, holder

    # The row ids a claim cites are data too, and `el()` translates a `title`
    # on the way in -- so they are assigned after construction, under the
    # opt-out that keeps the observer's attribute pass off them.
    assert 'cited.title = (claim.cites || []).join(", ");' in ROOM
    assert 'title: (claim.cites || []).join(", ")' not in ROOM
