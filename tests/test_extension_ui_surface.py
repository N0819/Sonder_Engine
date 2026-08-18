"""The browser registration surface, guarded the way `static/js` is guarded.

Source assertions rather than executed JavaScript, matching
`test_frontend_state_guards.py` -- node is not a declared dependency and
`docs/guides/TESTING.md` is explicit that the optional tier is the browser one.

Two failure modes are worth a test each, because both are silent and both are
the kind that gets found in play rather than in review:

* a registry added to `Sonder` but not to `_unregister`, so disabling an
  extension leaves its button, control or whole application on the page;
* a registry that a module extension's bound facade does not carry, so it
  works for a classic `ui.js` extension and is simply missing for a module one
  -- which the module author reads as "modules are broken".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = (ROOT / "static/js/extensions.js").read_text(encoding="utf-8")
STYLES = (ROOT / "static/styles.css").read_text(encoding="utf-8")


def _registration_methods():
    """Every `registerX`/`openX`/`closeX` method defined on the registry."""
    return set(re.findall(r"^  (register[A-Za-z]+|openView|closeView)\(",
                          EXTENSIONS, re.M))


class TestModuleFacade:
    def test_the_facade_is_derived_from_the_registry_not_from_a_list(self):
        """A hand-kept list is a second copy of the registration surface.

        The copy that falls behind is the one nobody notices: a call present on
        `Sonder` but missing from the list works for a classic `ui.js`
        extension and simply does not exist for a module one, which the module
        author reads as "modules are broken" rather than as one absent entry.
        """
        assert "_publicNames()" in EXTENSIONS
        assert "Object.keys(Sonder)" in EXTENSIONS
        assert "_PUBLIC" not in EXTENSIONS

    def test_the_derivation_publishes_every_registration_method(self):
        """The convention the derivation rests on: host-internal members wear a
        leading underscore, and every public one does not."""
        for name in _registration_methods():
            assert not name.startswith("_"), (
                f"{name} would be hidden from module extensions by the "
                f"underscore convention")

    def test_host_internals_stay_off_the_facade(self):
        """`_load`, `_unregister` and `_fault` are the host's, not an
        extension's -- an extension that could call `_unregister` could retire
        a rival, and one that could call `_fault` could frame it."""
        names = re.search(r"_publicNames\(\)\s*\{(.*?)\n  \},",
                          EXTENSIONS, re.S)
        assert names, "Sonder._publicNames no longer parses"

        assert 'name.charAt(0) !== "_"' in names.group(1)

    def test_the_facade_pins_the_owner_across_awaits(self):
        """The reason a facade exists at all.

        `_begin`/`_end` is ambient state. A module's `register` may await, and
        whatever runs during that await would otherwise register under this
        extension's name -- attribution silently crossing extensions is worse
        than no attribution, because it accuses the wrong author.
        """
        facade = re.search(r"_facade\(extId\)\s*\{(.*?)\n  \},", EXTENSIONS,
                           re.S)
        assert facade, "Sonder._facade no longer parses"
        body = facade.group(1)

        assert "const previous = Sonder._owner" in body
        assert "Sonder._owner = owner" in body
        assert "finally" in body

    def test_a_module_that_fails_to_import_is_charged_a_fault(self):
        """A broken module must not take the host's page with it."""
        loader = re.search(r"async _loadModule\(extId, href\)\s*\{(.*?)\n  \},",
                           EXTENSIONS, re.S)
        assert loader, "Sonder._loadModule no longer parses"
        body = loader.group(1)

        assert body.count("Sonder._fault(owner, error)") == 2
        assert "await import(href)" in body


class TestTeardown:
    def test_unregister_clears_every_registry(self):
        """Disable has to be able to take back everything an extension put up.

        The pre-existing note on `_unload` is honest that side effects survive
        it. That is the argument FOR host-owned registries, and it only holds
        while every registry is actually cleared here.
        """
        unregister = re.search(r"_unregister\(extId\)\s*\{(.*?)\n  \},",
                               EXTENSIONS, re.S)
        assert unregister, "Sonder._unregister no longer parses"
        body = unregister.group(1)

        for registry in ("_sidebar", "_topbar", "_views", "_composer",
                         "_steps", "_events"):
            assert registry in body, f"_unregister ignores Sonder.{registry}"

    def test_retiring_the_owner_of_the_open_view_returns_the_reader_to_it(self):
        """The worst failure this surface can produce.

        A view is full-window. If its owner is retired while it is open and the
        host does not close it, the reader is left looking at a dead
        application with no route back to their own story.
        """
        unregister = re.search(r"_unregister\(extId\)\s*\{(.*?)\n  \},",
                               EXTENSIONS, re.S)
        body = unregister.group(1)

        assert "Sonder._openView = null" in body
        assert "Sonder._renderView()" in body

    def test_the_host_only_removes_nodes_it_created(self):
        """Extension buttons share `#topactions` with the host's own.

        Clearing by `innerHTML` or by position would take the host's buttons
        with them, and the story toolbar is not this registry's to empty.
        """
        assert "data-ext-button" in EXTENSIONS
        assert "data-ext-composer" in EXTENSIONS
        assert "querySelectorAll(\"[data-ext-button]\")" in EXTENSIONS


class TestViewSurface:
    def test_a_view_is_removed_rather_than_hidden(self):
        """A hidden view keeps its timers, listeners and scroll position, and
        an extension retired mid-view would leave all three running."""
        render = re.search(r"_renderView\(\)\s*\{(.*?)\n  \},", EXTENSIONS,
                           re.S)
        assert render, "Sonder._renderView no longer parses"

        assert "existing.remove()" in render.group(1)

    def test_the_view_surface_is_styled_and_covers_the_transcript(self):
        """It covers rather than replaces, so closing it puts the reader back
        exactly where they were, mid-turn included."""
        assert "#ext-view" in STYLES
        assert "position: absolute" in STYLES

    def test_a_view_inherits_the_host_palette(self):
        """An extension that sets no colours must still look like the app it
        is inside, and must follow the reader's theme when they change it."""
        block = STYLES[STYLES.index("#ext-view"):]

        assert "var(--bg" in block
        assert "var(--fg" in block


class TestRefresh:
    def test_refresh_redraws_the_new_mount_points(self):
        """`Sonder.refresh()` is what an extension calls after changing its own
        state, and what the host calls after enabling one. A mount point it
        does not redraw is one that updates only by luck."""
        refresh = re.search(r"\n  refresh\(\)\s*\{(.*?)\n  \},", EXTENSIONS,
                            re.S)
        assert refresh, "Sonder.refresh no longer parses"
        body = refresh.group(1)

        assert "_renderTopBar" in body
        assert "_renderComposer" in body
        assert "_renderView" in body
