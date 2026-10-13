"""The page says, once, when the engine's files changed under the server.

`core.code_version` (2026-10-13): a server holds one version of the code; when
the disk no longer matches it, the boot and every turn's stream say so and the
host is told a restart would run the new code -- a warning, never a refusal.
"""
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def test_a_boot_on_changed_code_warns_once_and_marks_the_update_button(
        page: Page, ui_base_url: str) -> None:
    boot = dict(BOOTSTRAP, code={"stale": True, "count": 3, "changed": ["world/spatial_fov.py"],
                                 "started": 0, "files": 843})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def api(route):
        path = urlparse(route.request.url).path
        body = boot if path == "/api/bootstrap" else {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", api)
    page.goto(ui_base_url + "/static/index.html")
    toasts = page.locator("#toasts")
    expect(toasts).to_contain_text("changed after this server started (3 files)")
    expect(page.locator("#b-update")).to_have_class("code-stale")
    # a turn's stream saying the same thing adds no second warning
    page.evaluate("""() => handleEvt({type: 'notice', kind: 'code_changed', count: 3})""")
    expect(toasts.get_by_text("changed after this server started")).to_have_count(1)
    assert not errors, errors


def test_a_boot_on_current_code_says_nothing(page: Page, ui_base_url: str) -> None:
    boot = dict(BOOTSTRAP, code={"stale": False, "count": 0, "changed": [], "started": 0, "files": 843})

    def api(route):
        path = urlparse(route.request.url).path
        body = boot if path == "/api/bootstrap" else {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", api)
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof reportStaleCode === 'function'")
    expect(page.locator("#toasts")).not_to_contain_text("changed after this server started")
    expect(page.locator("#b-update")).not_to_have_class("code-stale")
