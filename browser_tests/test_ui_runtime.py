"""Behavioral contracts for the build-free replacement runtime."""

from __future__ import annotations

from playwright.sync_api import Page


def test_release_module_is_importable_without_classic_host_scripts(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const module = await import(`${base}/static/js/ui-next/release.js?release=wp02.1`);
          return {
            release: module.MODULE_RELEASE,
            hasClassicState: Object.hasOwn(window, "S"),
            hasReleaseCheck: typeof module.assertReleaseModules === "function",
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "release": "wp02.1",
        "hasClassicState": False,
        "hasReleaseCheck": True,
    }

