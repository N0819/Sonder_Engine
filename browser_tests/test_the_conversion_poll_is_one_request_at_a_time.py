"""The checkpoint-conversion card polls one request at a time, and only while
it is on the page.

Audit 2026-11-01 (`frontend_settings_world` F3). The card polled with
`setInterval(render, 1000)` and never awaited the previous request, while
`GET /api/maintenance/checkpoints` parsed the whole checkpoint store on every
call -- about 49 s on the owner's 2.8 GB store (measured `mode=ro`), so a
conversion kept ~49 of them in flight, enough to fill the server's thread
pool. Closing the dialog did not stop it, and each reopen added another
interval. The sibling embedding poll was fixed for exactly this.

Fully mocked at the network boundary, as `test_checkpoint_compaction_ui.py`.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page

from test_checkpoint_compaction_ui import _running


def _serve_running(page: Page, calls: list[str]) -> None:
    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/maintenance/checkpoints":
            calls.append(path)
            body = _running(10)
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)


def test_the_poll_stops_when_the_card_leaves_the_page(page: Page, ui_base_url: str) -> None:
    calls: list[str] = []
    _serve_running(page, calls)
    page.goto(f"{ui_base_url}/static/index.html")
    page.evaluate("() => { document.body.innerHTML = '';"
                  " document.body.append(checkpointCompactionBlock()); }")
    page.wait_for_function("() => document.body.innerText.includes('10 of 93')", timeout=8000)
    page.wait_for_timeout(1300)                    # at least one more poll
    assert len(calls) >= 2, calls
    # The dialog closes: the card is gone from the page.
    page.evaluate("() => { document.body.innerHTML = ''; }")
    page.wait_for_timeout(300)
    settled = len(calls)
    page.wait_for_timeout(2600)                    # two and a half poll intervals
    assert len(calls) == settled, f"{len(calls) - settled} polls after the card left"


def test_a_slow_status_call_is_never_overlapped(page: Page, ui_base_url: str) -> None:
    """Each answer takes 1.5 s; a one-second interval stacked them."""
    calls: list[str] = []
    _serve_running(page, calls)
    page.goto(f"{ui_base_url}/static/index.html")
    page.evaluate("""() => {
      const real = window.fetch;
      window.__inflight = 0; window.__most = 0;
      window.fetch = async (...args) => {
        if (!String(args[0]).includes('/api/maintenance/checkpoints')) return real(...args);
        window.__inflight += 1;
        window.__most = Math.max(window.__most, window.__inflight);
        try {
          await new Promise(r => setTimeout(r, 1500));
          return await real(...args);
        } finally { window.__inflight -= 1; }
      };
      document.body.innerHTML = '';
      document.body.append(checkpointCompactionBlock());
    }""")
    page.wait_for_function("() => document.body.innerText.includes('10 of 93')", timeout=8000)
    page.wait_for_timeout(4500)
    assert page.evaluate("() => window.__most") == 1
    assert len(calls) >= 2, calls                  # and it did go on polling
