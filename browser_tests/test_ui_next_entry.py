"""Browser contract for the isolated replacement application entry."""

from __future__ import annotations

from urllib.parse import urlparse

from playwright.sync_api import Page, expect


def test_ui_next_boots_as_an_isolated_native_module(
    page: Page, ui_base_url: str
) -> None:
    requested: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    page.add_init_script(
        """
        (() => {
          const nativeSetInterval = window.setInterval.bind(window);
          window.__uiNextIntervals = 0;
          window.setInterval = (...args) => {
            window.__uiNextIntervals += 1;
            return nativeSetInterval(...args);
          };
        })();
        """
    )
    page.on("request", lambda request: requested.append(urlparse(request.url).path))
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    response = page.goto(f"{ui_base_url}/static/ui-next.html")

    assert response is not None and response.ok
    expect(page.locator("html")).to_have_attribute("data-ui-next-ready", "true")
    expect(page.get_by_role("main")).to_be_visible()
    expect(page.get_by_role("heading", name="Play", level=1)).to_be_visible()
    expect(page.get_by_role("navigation", name="Primary")).to_be_visible()
    assert page.locator("script[type=module]").count() == 1
    assert page.evaluate("window.__uiNextIntervals") == 0
    assert page.evaluate("Object.hasOwn(window, 'S')") is False
    assert not any(path.startswith("/api/") for path in requested)
    assert "/static/ui-next.html" in requested
    assert "/static/js/ui-next/main.js" in requested
    assert "/static/js/ui/appearance-preflight.js" in requested
    assert "/static/css/ui/tokens.css" in requested
    assert all("/static/styles.css" != path for path in requested)
    assert all("/static/themes.css" != path for path in requested)
    assert all("/static/js/app.js" != path for path in requested)
    assert console_errors == []
    assert page_errors == []
