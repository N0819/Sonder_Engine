"""Capture reproducible current-UI screenshots and performance evidence.

The recorder serves the unbundled frontend exactly as browser tests do and
uses synthetic API fixtures only. It never reads a live database, credentials,
or player story content.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Iterator
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REQUIRED_JOURNEYS = {
    "play-empty",
    "play-populated",
    "library-scale",
    "settings",
    "new-story",
    "login",
    "guest-join",
}
REQUIRED_METRICS = {
    "boot_interactive_ms",
    "transcript_500_render_ms",
    "library_1000_render_ms",
    "effects_frame_ms",
    "navigation_dom_growth",
    "idle_api_requests",
}


def validate_baseline(data: dict) -> None:
    missing_journeys = sorted(REQUIRED_JOURNEYS - set(data.get("journeys", {})))
    if missing_journeys:
        raise ValueError(f"missing journeys: {', '.join(missing_journeys)}")
    missing_metrics = sorted(REQUIRED_METRICS - set(data.get("metrics", {})))
    if missing_metrics:
        raise ValueError(f"missing metrics: {', '.join(missing_metrics)}")
    for name, metric in data["metrics"].items():
        for key in ("median", "p95"):
            value = metric.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name}.{key} must be finite")
        if not isinstance(metric.get("runs"), int) or metric["runs"] < 1:
            raise ValueError(f"{name}.runs must be a positive integer")
    if data["metrics"]["idle_api_requests"]["p95"] != 0:
        raise ValueError("unexpected API traffic while idle")
    for name, journey in data["journeys"].items():
        if len(journey.get("viewport", [])) != 2:
            raise ValueError(f"{name} has no viewport metadata")
        digest = journey.get("screenshot_sha256", "")
        if len(digest) != 64:
            raise ValueError(f"{name} has no screenshot hash")


def derive_budgets(data: dict) -> dict[str, float | int]:
    metrics = data["metrics"]
    # Twenty percent absorbs normal local-machine noise while still making a
    # structural regression visible. Budgets are ceilings, never aspirations.
    return {
        "boot_interactive_p95_ms": round(metrics["boot_interactive_ms"]["p95"] * 1.20, 2),
        "transcript_500_render_p95_ms": round(metrics["transcript_500_render_ms"]["p95"] * 1.20, 2),
        "library_1000_render_p95_ms": round(metrics["library_1000_render_ms"]["p95"] * 1.20, 2),
        "effects_frame_p95_ms": round(metrics["effects_frame_ms"]["p95"] * 1.20, 2),
        "navigation_dom_growth_after_50": max(10, math.ceil(metrics["navigation_dom_growth"]["p95"] * 1.20)),
        "idle_api_requests": 0,
        "replacement_long_task_ms": 200,
    }


def _metric(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "median": round(statistics.median(ordered), 2),
        "p95": round(ordered[index], 2),
        "runs": len(ordered),
    }


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def _server(root: Path) -> Iterator[str]:
    handler = partial(_QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _turns(count: int) -> list[dict]:
    return [
        {
            "id": 1000 + index,
            "idx": index,
            "player_input": f"Player action {index}",
            "prose": f"Baseline narration {index}. The room remains quiet while the evidence recorder observes ordinary prose.",
            "stale": False,
            "frame_id": None,
        }
        for index in range(count)
    ]


def _chat(chat_id: int, name: str, count: int = 8) -> dict:
    return {
        "chat": {"id": chat_id, "name": name},
        "participants": [],
        "turns": _turns(count),
        "lorebook": None,
        "lorebooks": [],
        "frames": [],
    }


def _bootstrap(chats: list[dict]) -> dict:
    # Reuse the complete current browser fixture rather than inventing a
    # partial bootstrap that silently misses a field the application reads.
    from browser_tests.test_ui_smoke import BOOTSTRAP

    payload = copy.deepcopy(BOOTSTRAP)
    payload["chats"] = chats
    return payload


def _install_api(page, bootstrap: dict, chat_payloads: dict[int, dict], counter: dict[str, int]) -> None:
    def handle(route) -> None:
        path = urlparse(route.request.url).path
        counter[path] = counter.get(path, 0) + 1
        if path == "/api/bootstrap":
            body = bootstrap
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        elif path.startswith("/api/chats/") and path.count("/") == 3:
            try:
                body = chat_payloads.get(int(path.rsplit("/", 1)[1]), {})
            except ValueError:
                body = {}
        elif path == "/api/guest/state":
            body = {"joined": False}
        elif path == "/api/auth/status":
            body = {"setup_required": False, "authenticated": False}
        elif path == "/api/extensions":
            body = {
                "safe_mode": False,
                "load_errors": [],
                "extensions": [{
                    "id": "baseline-extension",
                    "name": "Baseline Extension",
                    "version": "1.0.0",
                    "enabled": True,
                    "provenance": "synthetic fixture",
                    "description": "Representative current extension card.",
                    "capabilities": {},
                }],
            }
        else:
            body = {}
        content_type = "application/javascript" if path.endswith(".js") else "application/json"
        route.fulfill(status=200, content_type=content_type, body=json.dumps(body))

    page.route("**/api/**", handle)


def _screenshot(page, path: Path, journeys: dict, name: str, viewport: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The current UI gives turns and dialogs a 120-200 ms entry animation.
    # Capturing immediately after DOM readiness records the animation's
    # opacity-zero first frame rather than the settled interface. Keep this
    # outside the performance measurements: it is screenshot stabilization,
    # not time the replacement is allowed to spend becoming interactive.
    page.wait_for_timeout(250)
    page.screenshot(path=str(path), full_page=False)
    journeys[name] = {
        "viewport": list(viewport),
        "screenshot": path.name,
        "screenshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _open_host_page(browser, base_url: str, viewport: tuple[int, int], bootstrap: dict, chats: dict[int, dict]):
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
    counter: dict[str, int] = {}
    _install_api(page, bootstrap, chats, counter)
    page.goto(f"{base_url}/")
    page.locator("#send").wait_for(state="visible")
    return page, counter


def _open_story(page, name: str, timeout_ms: int = 5000) -> None:
    item = page.get_by_label(f"Open {name}")
    box = item.bounding_box()
    if box is None or box["x"] < 0 or box["x"] >= page.viewport_size["width"]:
        page.locator("#b-menu").click()
    item.click(timeout=timeout_ms)
    page.wait_for_function(
        "name => document.querySelector('#chatname')?.textContent === name",
        arg=name,
        timeout=timeout_ms,
    )


def _capture_journeys(browser, base_url: str, screenshots: Path) -> dict:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    journeys: dict[str, dict] = {}
    chats = [{"id": 1, "name": "Baseline Story"}, {"id": 2, "name": "Second Story"}]
    payloads = {1: _chat(1, "Baseline Story"), 2: _chat(2, "Second Story")}

    page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap([]), {})
    _screenshot(page, screenshots / "desktop_empty_play.png", journeys, "play-empty", (1440, 900))
    page.close()

    for name, viewport, filename in (
        ("play-populated", (1440, 900), "desktop_play.png"),
        ("play-tablet", (1024, 768), "tablet_play.png"),
        ("play-mobile", (390, 844), "mobile_play.png"),
        ("play-narrow", (360, 640), "mobile_narrow_play.png"),
        ("play-landscape", (844, 390), "mobile_landscape_play.png"),
    ):
        page, counter = _open_host_page(browser, base_url, viewport, _bootstrap(chats), payloads)
        observed_limitation = None
        try:
            _open_story(page, "Baseline Story")
        except PlaywrightTimeoutError:
            if name != "play-landscape":
                raise
            item = page.get_by_label("Open Baseline Story")
            observed_limitation = {
                "finding": "story selection did not settle at 844x390",
                "chatname": page.locator("#chatname").text_content(),
                "modal_title": page.locator("#modaltitle").text_content(),
                "aria_current": item.get_attribute("aria-current"),
                "item_box": item.bounding_box(),
                "chat_request_count": counter.get("/api/chats/1", 0),
            }
        _screenshot(page, screenshots / filename, journeys, name, viewport)
        if observed_limitation:
            journeys[name]["observed_limitation"] = observed_limitation
        page.close()

    scale_chats = [{"id": index, "name": f"Library Story {index:04d}"} for index in range(1, 1001)]
    page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap(scale_chats), {})
    page.locator("#sidelist .item").first.wait_for()
    _screenshot(page, screenshots / "desktop_library_scale.png", journeys, "library-scale", (1440, 900))
    page.close()

    page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap(chats), payloads)
    page.locator("#b-theme").click()
    page.locator("#modal").wait_for(state="visible")
    _screenshot(page, screenshots / "desktop_settings_appearance.png", journeys, "settings", (1440, 900))
    page.close()

    page, _ = _open_host_page(browser, base_url, (1280, 640), _bootstrap(chats), payloads)
    page.locator("#b-theme").click()
    page.locator("#modal").wait_for(state="visible")
    _screenshot(page, screenshots / "short_settings_appearance.png", journeys, "settings-short", (1280, 640))
    page.close()

    page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap(chats), payloads)
    page.locator("#b-extensions").click()
    page.locator("#modal").wait_for(state="visible")
    page.get_by_text("Baseline Extension", exact=True).wait_for()
    _screenshot(page, screenshots / "desktop_extensions.png", journeys, "extensions", (1440, 900))
    page.close()

    long_chats = [{"id": 3, "name": "Five Hundred Turns"}]
    page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap(long_chats), {3: _chat(3, "Five Hundred Turns", 500)})
    _open_story(page, "Five Hundred Turns")
    page.locator("#msgs .turn").nth(499).wait_for()
    _screenshot(page, screenshots / "desktop_500_turns.png", journeys, "play-500", (1440, 900))
    page.close()

    page, _ = _open_host_page(browser, base_url, (390, 844), _bootstrap([]), {})
    page.evaluate("() => newChatWizard()")
    page.locator("#modal").wait_for(state="visible")
    _screenshot(page, screenshots / "mobile_new_story.png", journeys, "new-story", (390, 844))
    page.close()

    for name, url, filename in (
        ("login", "/static/login.html", "mobile_login.png"),
        ("guest-join", "/static/guest.html", "mobile_guest_join.png"),
    ):
        page = browser.new_page(viewport={"width": 390, "height": 844})
        counter: dict[str, int] = {}
        _install_api(page, {}, {}, counter)
        page.goto(base_url + url)
        page.locator("body").wait_for(state="visible")
        _screenshot(page, screenshots / filename, journeys, name, (390, 844))
        page.close()

    return journeys


def _measure(browser, base_url: str) -> dict:
    boot: list[float] = []
    transcript: list[float] = []
    library: list[float] = []
    for _ in range(3):
        start = time.perf_counter()
        page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap([]), {})
        boot.append((time.perf_counter() - start) * 1000)
        page.close()

        chats = [{"id": 1, "name": "Long Story"}]
        page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap(chats), {1: _chat(1, "Long Story", 500)})
        start = time.perf_counter()
        _open_story(page, "Long Story")
        page.locator("#msgs .turn").nth(499).wait_for()
        transcript.append((time.perf_counter() - start) * 1000)
        page.close()

        scale_chats = [{"id": index, "name": f"Story {index:04d}"} for index in range(1, 1001)]
        start = time.perf_counter()
        page, _ = _open_host_page(browser, base_url, (1440, 900), _bootstrap(scale_chats), {})
        page.locator("#sidelist .item").nth(999).wait_for()
        library.append((time.perf_counter() - start) * 1000)
        page.close()

    chats = [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}]
    payloads = {1: _chat(1, "First", 5), 2: _chat(2, "Second", 5)}
    page, counter = _open_host_page(browser, base_url, (1440, 900), _bootstrap(chats), payloads)
    initial_nodes = page.evaluate("document.getElementsByTagName('*').length")
    growth: list[float] = []
    for index in range(50):
        chat_id = 1 if index % 2 == 0 else 2
        page.evaluate("id => openChat(id)", chat_id)
        page.locator("#chatname").filter(has_text="First" if chat_id == 1 else "Second").wait_for()
        growth.append(float(page.evaluate("document.getElementsByTagName('*').length") - initial_nodes))

    page.evaluate("() => weatherFxApply({weather_visible:true, precipitation:'rain', intensity:'heavy', visible_reach:'far', sky:'overcast'})")
    frames = page.evaluate(
        """() => new Promise(resolve => {
          const samples = []; let last = performance.now();
          function frame(now) {
            samples.push(now - last); last = now;
            if (samples.length >= 60) resolve(samples); else requestAnimationFrame(frame);
          }
          requestAnimationFrame(frame);
        })"""
    )
    before_idle = sum(counter.values())
    page.wait_for_timeout(2000)
    idle = float(sum(counter.values()) - before_idle)
    page.close()

    return {
        "boot_interactive_ms": _metric(boot),
        "transcript_500_render_ms": _metric(transcript),
        "library_1000_render_ms": _metric(library),
        "effects_frame_ms": _metric([float(value) for value in frames]),
        "navigation_dom_growth": _metric(growth),
        "idle_api_requests": _metric([idle]),
    }


def _budgets_markdown(data: dict, budgets: dict) -> str:
    journeys = "\n".join(
        f"| `{name}` | {item['viewport'][0]}×{item['viewport'][1]} | `{item['screenshot']}` | `{item['screenshot_sha256']}` |"
        for name, item in sorted(data["journeys"].items())
    )
    metrics = "\n".join(
        f"| `{name}` | {value['median']} | {value['p95']} | {value['runs']} |"
        for name, value in sorted(data["metrics"].items())
    )
    budget_rows = "\n".join(f"| `{name}` | {value} |" for name, value in sorted(budgets.items()))
    limitations = []
    for name, item in sorted(data["journeys"].items()):
        if finding := item.get("observed_limitation"):
            limitations.append(
                f"- `{name}`: {finding['finding']}; chat request count "
                f"{finding['chat_request_count']}, selected state "
                f"`{finding['aria_current']}`, visible title "
                f"`{finding['chatname']}`, opened dialog "
                f"`{finding.get('modal_title', '')}`."
            )
    limitation_block = "\n".join(limitations) or "- None observed by this recorder."
    return f"""# Current UI baseline and release budgets

**Baseline commit:** `{data['commit']}`  
**Browser:** {data['browser']['name']} {data['browser']['version']}  
**Platform:** {data['platform']}

All content is synthetic. No live database, credential, join code, or player
story is read. Candidate screenshots are reference material and are not part of
this current-source baseline.

## Captured journeys

| Journey | Viewport | Screenshot | SHA-256 |
|---|---:|---|---|
{journeys}

## Measurements

Times are milliseconds. Boot, 500-turn transcript, and 1,000-story list use
three fresh pages; frame cadence uses 60 animation frames; navigation growth
records each of 50 story switches; idle traffic observes two seconds after the
page settles.

| Metric | Median | p95 | Runs/samples |
|---|---:|---:|---:|
{metrics}

## Observed current limitations

{limitation_block}

## Release ceilings

| Budget | Ceiling |
|---|---:|
{budget_rows}

Boot, long transcript, large Library, and effects ceilings are the conservative
current p95 plus 20 percent. Any tighter number would make normal measurement
noise fail the replacement before it changes behavior. The replacement permits
zero steady-state API polling while idle, at most the recorded/buffered DOM
growth after 50 navigation cycles, and no replacement-attributable long task
above 200 ms. Supported viewport/zoom evidence must show no continuous overlap,
clipping, horizontal page overflow, hidden essential action, or mobile
capability deletion.

A budget can be exceeded only through an explicit evidence-backed deviation in
the traceability matrix; historical candidate measurements cannot waive it.
"""


def capture(root: Path, output: Path, commit: str) -> dict:
    from playwright.sync_api import sync_playwright

    screenshots = output / "screenshots"
    with _server(root) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            data = {
                "commit": commit,
                "browser": {"name": "chromium", "version": browser.version},
                "platform": platform.platform(),
                "fixture_sizes": {"transcript_turns": 500, "library_records": 1000, "navigation_cycles": 50},
                "journeys": _capture_journeys(browser, base_url, screenshots),
                "metrics": _measure(browser, base_url),
            }
        finally:
            browser.close()
    validate_baseline(data)
    budgets = derive_budgets(data)
    output.mkdir(parents=True, exist_ok=True)
    (output / "current-ui-baseline.json").write_text(
        json.dumps({**data, "budgets": budgets}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output.parent / "BASELINE_AND_BUDGETS.md").write_text(
        _budgets_markdown(data, budgets).rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    output = args.output or args.root / "docs" / "design" / "sonder-ui-replacement" / "baseline"
    capture(args.root.resolve(), output.resolve(), args.commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
