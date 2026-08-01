"""The legacy-checkpoint conversion card, in a real browser.

This card is the one piece of maintenance UI that can rewrite rollback
history, and it was written against nothing but `node --check`. Its interesting
parts are all behaviour a syntax checker cannot see: a poll loop that has to
start when a run is in flight and stop when it is not, a determinate progress
bar, and a button that must not be clickable twice.

Fully mocked at the network boundary, so nothing here touches a database.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect


def _mount(page: Page, states: list[dict]) -> None:
    """Serve `/api/maintenance/checkpoints` from a queue of states.

    A list rather than one payload because the point is the TRANSITION: the
    card polls while a conversion runs and settles when it ends, and a single
    static response cannot tell a working poll loop from one that never fires.
    """
    remaining = list(states)

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/maintenance/checkpoints":
            body = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        elif path == "/api/maintenance/checkpoints/compact":
            body = {"started": True}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)


def _open_card(page: Page, ui_base_url: str, states: list[dict]) -> None:
    _mount(page, states)
    page.goto(f"{ui_base_url}/static/index.html")
    # Mount the card alone rather than driving the whole updates modal: this
    # file owns the card's behaviour, not the modal's routing.
    page.evaluate("() => { document.body.innerHTML = '';"
                  " document.body.append(checkpointCompactionBlock()); }")


IDLE_LEGACY = {"checkpoints": 93, "legacy": 93,
               "bytes": 448_600_000, "legacy_bytes": 448_600_000,
               "progress": {"running": False, "error": ""}}
IDLE_DONE = {"checkpoints": 93, "legacy": 0,
             "bytes": 44_000_000, "legacy_bytes": 0,
             "progress": {"running": False, "error": ""}}


def _running(done: int) -> dict:
    return {"checkpoints": 93, "legacy": 93, "bytes": 448_600_000,
            "legacy_bytes": 448_600_000,
            "progress": {"running": True, "done": done, "total": 93,
                         "rewritten": done, "bytes_before": 100_000_000,
                         "bytes_after": 10_000_000, "error": ""}}


def test_it_offers_conversion_when_checkpoints_are_legacy(
        page: Page, ui_base_url: str) -> None:
    _open_card(page, ui_base_url, [IDLE_LEGACY])
    expect(page.get_by_text(
        "Convert legacy checkpoints to the leaner format")).to_be_visible()
    # The host is told the scale before deciding, in their own units.
    expect(page.get_by_text("93 of 93 checkpoints", exact=False)).to_be_visible()
    expect(page.get_by_text("448.6 MB", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Convert now")).to_be_visible()


def test_it_says_nothing_to_do_when_already_converted(
        page: Page, ui_base_url: str) -> None:
    _open_card(page, ui_base_url, [IDLE_DONE])
    expect(page.get_by_text("All 93 checkpoints are in the current format",
                            exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Convert now")).to_have_count(0)


def test_the_progress_bar_is_determinate_and_advances(
        page: Page, ui_base_url: str) -> None:
    """The count is known before the run starts, so this reports a real
    fraction rather than an indeterminate spinner."""
    _open_card(page, ui_base_url, [_running(20), _running(60), IDLE_DONE])

    expect(page.get_by_text("20 of 93 checkpoints (22%)",
                            exact=False)).to_be_visible()
    bar = "() => document.querySelector('div[style*=\"width:\"]').style.width"
    assert page.evaluate(bar) == "22%"

    # The poll loop is the part `node --check` cannot see: it must advance with
    # no further interaction.
    page.wait_for_function(
        "() => document.body.innerText.includes('60 of 93')", timeout=8000)
    assert page.evaluate(bar) == "65%"


def test_the_poll_stops_when_the_run_finishes(
        page: Page, ui_base_url: str) -> None:
    """A timer left running after the work ends polls forever."""
    _open_card(page, ui_base_url, [_running(90), IDLE_DONE])
    page.wait_for_function(
        "() => document.body.innerText.includes('current format')", timeout=8000)
    before = page.evaluate("() => document.body.innerText")
    page.wait_for_timeout(2500)          # two poll intervals
    assert page.evaluate("() => document.body.innerText") == before


def test_the_button_cannot_be_clicked_twice(
        page: Page, ui_base_url: str) -> None:
    """Starting a conversion twice is exactly what a host does when a slow
    request makes the button look dead."""
    _open_card(page, ui_base_url, [IDLE_LEGACY])
    page.get_by_role("button", name="Convert now").click()
    expect(page.get_by_role("button", name="Starting…")).to_be_disabled()


def test_a_failed_run_says_what_survived(page: Page, ui_base_url: str) -> None:
    """After a failed rewrite of rollback history there is only one question
    worth answering: did I lose anything."""
    failed = {"checkpoints": 93, "legacy": 40, "bytes": 200_000_000,
              "legacy_bytes": 190_000_000,
              "progress": {"running": False, "error": "disk full",
                           "done": 53, "total": 93}}
    _open_card(page, ui_base_url, [failed])
    expect(page.get_by_text("Conversion stopped: disk full")).to_be_visible()
    expect(page.get_by_text("Nothing was lost", exact=False)).to_be_visible()
    # And it still offers to resume.
    expect(page.get_by_role("button", name="Convert now")).to_be_visible()


def test_it_survives_a_dead_endpoint(page: Page, ui_base_url: str) -> None:
    """A maintenance card must not take the updates modal down with it."""
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/api/**", lambda route: route.fulfill(
        status=500, content_type="application/json", body='{"detail":"nope"}'))
    page.goto(f"{ui_base_url}/static/index.html")
    page.evaluate("() => { document.body.innerHTML = '';"
                  " document.body.append(checkpointCompactionBlock()); }")
    expect(page.get_by_text("Could not check", exact=False)).to_be_visible()
    assert not errors, errors
