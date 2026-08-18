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
SETTINGS = (ROOT / "static/js/settings.js").read_text(encoding="utf-8")


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

    def test_the_facade_carries_namespaces_as_well_as_calls(self):
        """`chats` is a namespace, not a call, and the first of its kind.

        The derivation filtered on `typeof === "function"`, so a namespace
        added to `Sonder` reached classic `ui.js` extensions and was simply
        absent for module ones -- the exact failure the derivation exists to
        prevent, arriving through the one shape it did not cover.
        """
        assert "_publicNamespaces()" in EXTENSIONS

        facade = re.search(r"_facade\(extId\)\s*\{(.*?)\n  \},", EXTENSIONS,
                           re.S)
        assert facade, "Sonder._facade no longer parses"

        assert "_publicNamespaces()" in facade.group(1)

    def test_namespaces_are_not_owner_bound_and_the_reason_is_written_down(
            self):
        """Owner binding exists so a CALLBACK can be charged to whoever
        registered it. A namespace method is a fetch: no callback, nobody to
        charge. Binding it would be cargo, and an unexplained difference
        between the two loops is one somebody later 'fixes'."""
        namespaces = re.search(r"_publicNamespaces\(\)\s*\{(.*?)\n  \},",
                               EXTENSIONS, re.S)
        assert namespaces, "Sonder._publicNamespaces no longer parses"

        assert 'name.charAt(0) !== "_"' in namespaces.group(1)
        assert "not registrations" in EXTENSIONS


class TestSettingsSections:
    """An extension's configuration, in its own card in the 🧩 menu.

    Not in the host's API settings: an extension's configuration is
    install-scoped (`api.settings`), and the one place a reader is already
    looking at this extension is the row carrying its name, version and enable
    switch.
    """

    def test_sections_are_cleared_when_their_extension_retires(self):
        unregister = re.search(r"_unregister\(extId\)\s*\{(.*?)\n  \},",
                               EXTENSIONS, re.S)
        assert unregister, "Sonder._unregister no longer parses"

        assert "_settings" in unregister.group(1)

    def test_a_disabled_extension_renders_no_section(self):
        """Its registrations are cleared, so there is nothing to render -- and
        a section that outlived its owner would be configuring code that is not
        running."""
        assert "enabled ? extensionSettingsSections(ext.id) : []" in SETTINGS

    def test_a_section_is_rendered_on_first_open_not_on_menu_open(self):
        """A section that fetches would otherwise cost a round trip per
        installed extension every time somebody glances at the list."""
        sections = re.search(
            r"function extensionSettingsSections\(extId\)\s*\{(.*?)\n\}",
            SETTINGS, re.S)
        assert sections, "extensionSettingsSections no longer parses"
        body = sections.group(1)

        assert "let drawn = false" in body
        assert "Sonder._safe(section.owner, section.render, body)" in body

    def test_the_section_chrome_is_styled(self):
        assert ".ext-settings__body" in STYLES


class TestNotices:
    """The standing counterpart of a toast.

    A toast acknowledges what the reader just did and is gone in four seconds
    whether or not it was read. A campaign layer needs to say "your objective
    changed while you were reading" and have it still be there when the reader
    looks up.
    """

    def test_notices_are_cleared_when_their_extension_retires(self):
        """The failure every registry here shares: a retired extension leaving
        part of its interface on the page."""
        unregister = re.search(r"_unregister\(extId\)\s*\{(.*?)\n  \},",
                               EXTENSIONS, re.S)
        assert unregister, "Sonder._unregister no longer parses"

        assert "_notices" in unregister.group(1)

    def test_a_notice_can_be_taken_down_by_whoever_raised_it(self):
        """A centre whose entries only the reader can dismiss tells them about
        problems that were fixed an hour ago. `notify` returns an id."""
        assert "dismissNotice(id)" in EXTENSIONS
        assert "return id;" in EXTENSIONS

    def test_notices_are_bounded(self):
        """One raised per beat would otherwise fill the column with history."""
        assert "_noticeCap" in EXTENSIONS

    def test_a_notice_action_is_charged_to_its_owner(self):
        """Same rule as every other extension callback: a throw inside one
        counts toward that extension's three strikes rather than reading as a
        host defect."""
        render = re.search(r"_renderNotices\(\)\s*\{(.*?)\n  \},",
                           EXTENSIONS, re.S)
        assert render, "Sonder._renderNotices no longer parses"

        assert "Sonder._safe(notice.owner, notice.onClick)" in render.group(1)

    def test_the_notice_column_is_styled(self):
        """Registered chrome with no stylesheet is chrome that lands unstyled
        in the corner of somebody's screen."""
        assert "#ext-notices" in STYLES
        assert ".ext-notice" in STYLES


class TestChatLifecycle:
    """The lifecycle namespace, and the refusal inside it."""

    def test_it_declares_the_calls_an_adapter_needs(self):
        chats = re.search(r"\n  chats: \{(.*?)\n  \},", EXTENSIONS, re.S)
        assert chats, "Sonder.chats no longer parses"
        body = chats.group(1)

        for call in ("list(", "get(", "create(", "open(", "branch(",
                     "narration(", "selectNarration(", "reroll("):
            assert call in body, call

    def test_there_is_no_post_message_call(self):
        """Not an oversight. Prose comes out of the pipeline, and text injected
        as though the narrator wrote it is narration nothing earned."""
        chats = re.search(r"\n  chats: \{(.*?)\n  \},", EXTENSIONS, re.S)
        assert chats, "Sonder.chats no longer parses"
        body = chats.group(1)

        assert "postAssistant" not in body
        assert "postMessage" not in body

    def test_open_is_guarded_against_a_page_without_the_chat_module(self):
        """An extension view can be mounted on a page that never loaded it."""
        chats = re.search(r"\n  chats: \{(.*?)\n  \},", EXTENSIONS, re.S)

        assert 'typeof openChat !== "function"' in chats.group(1)


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
