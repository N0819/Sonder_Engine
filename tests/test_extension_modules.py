"""ES module entries: `capabilities.ui.module`.

The classic `ui.js` path concatenates every enabled extension's entry into one
script, which is right for a panel and impossible for an extension built as a
module graph -- `import` in a classic script is a SyntaxError, and per the
bundle's own containment note a top-level throw takes down every extension
after it. An extension of any size is a module graph, so without this a
total-conversion extension cannot be loaded at all.

What is pinned here is the loading CONTRACT rather than the browser's module
semantics, which no Python test can observe: that a module entry contributes a
loader line and never its source, that the source is served from `/asset/` so
its own relative imports resolve, and that declaring one is enough to make an
extension `code`-trusted.
"""

from __future__ import annotations

import json

import pytest

import extension_runtime

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _enable, _write_extension, ext_root,
)


MODULE_SOURCE = (
    "import { thing } from './helper.js';\n"
    "export function register(sonder) { sonder.registerView(thing); }\n"
)


def _module_extension(root, ext_id="modular", **capabilities):
    caps = {"ui": {"module": "src/index.js"}}
    caps.update(capabilities)
    _write_extension(root, ext_id, {
        "id": ext_id, "version": "1.0.0", "ext_api": 1, "name": "Modular",
        "capabilities": caps,
    }, {
        "src/index.js": MODULE_SOURCE,
        "src/helper.js": "export const thing = { id: 'x', render() {} };\n",
    })
    return ext_id


class TestModuleEntries:
    def test_a_module_entry_is_served_as_a_loader_line_not_as_source(
            self, temp_db, ext_root):
        """Inlining the source is the bug this whole path exists to avoid.

        The bundle is a classic script. Putting `import` in it is a SyntaxError
        that kills not just this extension but every one concatenated after it.
        """
        _module_extension(ext_root)
        _enable("modular")

        script = extension_runtime.extension_script("modular")

        assert "_loadModule" in script
        assert "/api/extensions/modular/asset/src/index.js" in script
        assert "import" not in script

    def test_the_bundle_carries_the_loader_line_too(self, temp_db, ext_root):
        """Page load and hot load must agree, or enable behaves differently
        from a reload and only one of the two ever gets tested by hand."""
        _module_extension(ext_root)
        _enable("modular")

        bundle = extension_runtime.ui_bundle()

        assert "_loadModule" in bundle
        assert "import" not in bundle

    def test_the_loader_line_is_json_encoded(self, temp_db, ext_root):
        """The id and href are interpolated into JavaScript source.

        They are host-controlled and already validated against `EXTENSION_ID`,
        so this is not the last line of defence -- but a value interpolated raw
        into a script is a habit that outlives the validation that made it
        safe.
        """
        _module_extension(ext_root)
        _enable("modular")

        script = extension_runtime.extension_script("modular")

        assert json.dumps("modular") in script
        assert json.dumps("/api/extensions/modular/asset/src/index.js") in script

    def test_a_disabled_module_extension_serves_nothing(self, temp_db,
                                                        ext_root):
        _module_extension(ext_root)
        _enable()

        assert extension_runtime.extension_script("modular") == ""
        assert "modular" not in extension_runtime.ui_bundle()

    def test_a_module_and_a_classic_entry_can_coexist(self, temp_db, ext_root):
        """A migration moves one file at a time; refusing both forces a
        big-bang rewrite to adopt modules at all."""
        _write_extension(ext_root, "both", {
            "id": "both", "version": "1.0.0", "ext_api": 1, "name": "Both",
            "capabilities": {"ui": {"js": "panel.js", "module": "app.js"}},
        }, {
            "panel.js": "Sonder.registerSidebarTab({id:'a',label:'A',render(){}});",
            "app.js": "export function register(sonder) {}\n",
        })
        _enable("both")

        script = extension_runtime.extension_script("both")

        assert "registerSidebarTab" in script
        assert "_loadModule" in script

    def test_declaring_a_module_makes_the_extension_code_trusted(
            self, temp_db, ext_root):
        """The consent dialog's wording is computed from this.

        A module entry is code by every measure that matters, and an extension
        that shipped one while reading as `data` would be consented to on a
        sentence that is simply false.
        """
        _write_extension(ext_root, "declared", {
            "id": "declared", "version": "1.0.0", "ext_api": 1,
            "name": "Declared",
            "capabilities": {"ui": {"module": "app.js"}},
        })

        installed = extension_runtime.installed_extensions(refresh=True)

        assert installed["declared"].trust == "code"

    def test_an_mjs_file_in_the_tree_is_code_even_undeclared(self, temp_db,
                                                             ext_root):
        """Declared OR present, the same rule `.js` already followed.

        `.mjs` is the extension a module graph most often uses, and it was the
        one suffix the present-file sweep did not look for -- so an extension
        made entirely of `.mjs` read as `data` and was consented to as such.
        """
        _write_extension(ext_root, "quiet", {
            "id": "quiet", "version": "1.0.0", "ext_api": 1, "name": "Quiet",
            "capabilities": {},
        }, {"engine.mjs": "export const x = 1;\n"})

        installed = extension_runtime.installed_extensions(refresh=True)

        assert installed["quiet"].trust == "code"

    def test_module_source_is_reachable_through_the_asset_path(self, temp_db,
                                                               ext_root):
        """Relative imports resolve against the module's own URL, so the whole
        tree has to be fetchable -- and containment-checked when it is."""
        _module_extension(ext_root)
        _enable("modular")

        entry = extension_runtime.asset_path("modular", "src/index.js")
        helper = extension_runtime.asset_path("modular", "src/helper.js")

        assert entry.read_text(encoding="utf-8") == MODULE_SOURCE
        assert "export const thing" in helper.read_text(encoding="utf-8")

    def test_an_import_may_not_escape_the_extension_directory(self, temp_db,
                                                              ext_root):
        """A module's imports are strings it chooses, so the asset route is
        now an import resolver as well as a file server."""
        _module_extension(ext_root)
        _enable("modular")

        with pytest.raises(extension_runtime.ExtensionError):
            extension_runtime.asset_path("modular", "../secrets.js")

    def test_safe_mode_serves_no_module_loader(self, temp_db, ext_root,
                                               monkeypatch):
        """The escape hatch has to cover the path that can break the page.

        A module loader line is still code the host asked not to run, and it is
        the one entry that survives being wrong long enough to be fetched.
        """
        _module_extension(ext_root)
        _enable("modular")
        monkeypatch.setenv("SONDER_EXTENSIONS_SAFE", "1")

        assert extension_runtime.extension_script("modular") == ""
        assert extension_runtime.ui_bundle() == ""
