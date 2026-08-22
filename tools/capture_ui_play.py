"""Capture deterministic WP-04 Play-core evidence from synthetic stories."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "g3"
SCREENSHOTS = OUTPUT / "screenshots"
RENDER_BUDGET_MS = 198.73


def turn(turn_id: int, idx: int, *, frame_id: int | None = None) -> dict:
    return {
        "id": turn_id,
        "idx": idx,
        "player_input": f"I follow the keeper past shelf {idx + 1}.",
        "prose": (
            f"Turn {idx + 1}. Rain crosses the high windows in silver threads. "
            "The archive keeper turns one page, then looks up and waits."
        ),
        "stale": False,
        "stale_from": None,
        "prose_stale": False,
        "frame_id": frame_id,
        "speech": [{"speaker": "Mara", "exact_quote": "Wait."}],
    }


def story(turn_count: int = 12) -> dict:
    return {
        "chat": {"id": 1, "name": "The Lantern Archive", "scenario": ""},
        "turns": [turn(index + 1, index) for index in range(turn_count)],
        "frames": [
            {"id": None, "label": "Present", "kind": "present", "ordinal": 0},
            {"id": 5, "label": "Courtyard", "kind": "branch", "ordinal": 1},
        ],
        "participants": [],
        "dialogue_colors": {"Mara": "rgb(110, 191, 153)"},
        "lorebook": None,
        "lorebooks": [],
        "embedding_bank": None,
        "story_language": "en",
    }


def bootstrap(*, japanese: bool = False) -> dict:
    messages = {}
    if japanese:
        messages = json.loads(
            (ROOT / "language_packs" / "ja" / "ui.json").read_text(encoding="utf-8")
        )
    return {
        "ui_language": "ja" if japanese else "en",
        "ui_direction": "ltr",
        "ui_messages": messages,
        "chats": [
            {"id": 1, "name": "The Lantern Archive"},
            {"id": 2, "name": "Winter Road"},
        ],
        "characters": [],
        "personas": [],
        "lorebooks": [],
        "providers": [],
        "language_packs": [],
        "extensions": [],
        "extension_errors": [],
        "extension_lanes": [],
    }


CASES = (
    ("no-story", 1280, 800, "#/play", "none", 0, False),
    ("desktop", 1440, 900, "#/play?chat=1", "none", 12, False),
    ("medium", 1024, 768, "#/play?chat=1", "none", 12, False),
    ("tablet", 768, 1024, "#/play?chat=1", "none", 12, False),
    ("phone", 390, 844, "#/play?chat=1", "none", 12, False),
    ("narrow-phone", 360, 800, "#/play?chat=1", "none", 12, False),
    ("landscape", 844, 390, "#/play?chat=1", "none", 12, False),
    ("short-desktop", 1024, 600, "#/play?chat=1", "none", 12, False),
    ("zoom-equivalent", 640, 360, "#/play?chat=1", "none", 12, False),
    ("turn-500", 1440, 900, "#/play?chat=1", "none", 500, False),
    ("japanese", 390, 844, "#/play?chat=1", "none", 12, True),
    ("scrollback", 1280, 800, "#/play?chat=1", "scrollback", 80, False),
    ("versions", 1280, 800, "#/play?chat=1", "versions", 1, False),
    ("reroll-warning", 390, 844, "#/play?chat=1", "reroll", 1, False),
    ("turn-details", 1280, 800, "#/play?chat=1", "details", 1, False),
    ("story-actions", 1280, 800, "#/play?chat=1", "story-actions", 12, False),
    ("recoverable-error", 390, 844, "#/play?chat=1", "failure", 12, False),
    ("offline-story", 390, 844, "#/play?chat=1", "offline-story", 0, False),
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def fulfill_json(route: Route, payload: object, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash() -> str:
    digest = hashlib.sha256()
    files = [
        path
        for base in (ROOT / "static" / "css" / "ui", ROOT / "static" / "js" / "ui-next")
        for path in base.rglob("*")
        if path.is_file()
    ]
    files.extend(
        [
            ROOT / "static" / "ui-next.html",
            ROOT / "language_packs" / "en" / "ui.json",
            ROOT / "language_packs" / "ja" / "ui.json",
        ]
    )
    for path in sorted(files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def route_case(page: Page, payload: dict, boot: dict, action: str) -> None:
    page.route("**/api/bootstrap", lambda route: fulfill_json(route, boot))
    if action == "offline-story":
        page.route("**/api/chats/1", lambda route: route.abort("failed"))
    else:
        page.route("**/api/chats/1", lambda route: fulfill_json(route, payload))
    page.route(
        "**/api/turns/*/narration",
        lambda route: fulfill_json(
            route,
            {
                "variants": [
                    {"id": 1, "active": True, "prose": "The first telling."},
                    {"id": 2, "active": False, "prose": "The second telling."},
                ]
            },
        ),
    )
    page.route(
        "**/api/turns/*/pipeline",
        lambda route: fulfill_json(
            route,
            {
                "steps": [
                    {"key": "director_interpret", "label": "Read the action"},
                    {"key": "narrator", "label": "Write the scene"},
                ]
            },
        ),
    )
    if action == "failure":
        page.route("**/api/chats/1/turns", lambda route: route.abort("failed"))


def apply_action(page: Page, action: str) -> None:
    if action == "scrollback":
        page.locator("[data-play-transcript]").evaluate("node => { node.scrollTop = 900; }")
    elif action == "versions":
        page.get_by_role("button", name="Versions", exact=True).click()
        page.get_by_role("dialog", name="Versions").get_by_text(
            "The first telling.", exact=True
        ).wait_for()
    elif action == "reroll":
        page.get_by_role("button", name="Reroll", exact=True).click()
        page.get_by_role("dialog", name="Reroll this turn?").wait_for()
    elif action == "details":
        page.get_by_role("button", name="More", exact=True).click()
        page.get_by_role("menuitem", name="Turn details", exact=True).click()
        page.get_by_role("dialog", name="Turn details").get_by_text(
            "Write the scene", exact=True
        ).wait_for()
    elif action == "story-actions":
        page.get_by_role("button", name="Story actions").click()
    elif action == "failure":
        box = page.get_by_role("textbox", name="What do you do or say?")
        box.fill("Keep this draft")
        page.get_by_role("button", name="Send", exact=True).click()
        page.get_by_role("button", name="Retry", exact=True).wait_for()
    elif action == "offline-story":
        page.get_by_role("heading", name="Sonder is offline").wait_for()


def inspect_page(page: Page, requested: list[str], measured_render_ms: float) -> dict:
    metrics = page.evaluate(
        """() => {
          const visible = node => {
            const rect = node.getBoundingClientRect();
            return rect.width > 1 && rect.height > 1 && rect.bottom > 0
              && rect.right > 0 && rect.top < innerHeight && rect.left < innerWidth;
          };
          const controls = [...document.querySelectorAll('button,input,select,textarea,a[href]')]
            .filter(visible);
          const prose = document.querySelector('.ui-play__prose');
          const transcript = document.querySelector('[data-play-transcript]');
          const storyHeader = document.querySelector('.ui-play__story-header');
          const composer = document.querySelector('[data-play-composer]');
          const targetRows = controls.map(node => {
            const rect = node.getBoundingClientRect();
            return {
              label: node.getAttribute('aria-label') || node.textContent.trim(),
              width: Math.round(rect.width * 100) / 100,
              height: Math.round(rect.height * 100) / 100,
            };
          });
          return {
            state: document.documentElement.dataset.uiNextState,
            layout_state: document.documentElement.dataset.layoutState,
            route: location.hash,
            language: document.documentElement.lang,
            window_scroll_y: scrollY,
            horizontal_overflow_px: document.documentElement.scrollWidth
              - document.documentElement.clientWidth,
            minimum_visible_target_px: controls.length
              ? Math.min(...controls.map(node => Math.min(
                node.getBoundingClientRect().width,
                node.getBoundingClientRect().height,
              ))) : null,
            undersized_visible_targets: targetRows.filter(row => (
              Math.min(row.width, row.height) < 44
            )),
            turn_count: document.querySelectorAll('[data-turn-id]').length,
            dom_count: document.querySelectorAll('*').length,
            transcript_scroll_top: transcript?.scrollTop ?? null,
            transcript_scroll_height: transcript?.scrollHeight ?? null,
            prose_geometry: prose ? {
              width: prose.getBoundingClientRect().width,
              height: prose.getBoundingClientRect().height,
              text: prose.textContent,
            } : null,
            story_header_geometry: storyHeader?.getBoundingClientRect().toJSON() ?? null,
            composer_geometry: composer?.getBoundingClientRect().toJSON() ?? null,
            visible_actions: targetRows.map(row => row.label).filter(Boolean),
            focus: document.activeElement?.getAttribute('aria-label')
              || document.activeElement?.textContent?.trim() || null,
            classic_global: Object.hasOwn(window, 'S'),
            sensitive_text: /password|api[_ -]?key|join code|cookie|session=/i
              .test(document.body.textContent),
          };
        }"""
    )
    metrics["render_budget_ms"] = RENDER_BUDGET_MS
    metrics["render_within_budget"] = measured_render_ms <= RENDER_BUDGET_MS
    metrics["api_requests"] = sorted(
        urlparse(url).path for url in requested if "/api/" in urlparse(url).path
    )
    if metrics["minimum_visible_target_px"] is not None:
        metrics["minimum_visible_target_px"] = round(
            metrics["minimum_visible_target_px"], 2
        )
    return metrics


def capture() -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    results = []
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        browser_version = browser.version
        for case_id, width, height, route_hash, action, count, japanese in CASES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.emulate_media(reduced_motion="reduce")
            requested: list[str] = []
            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("request", lambda request, rows=requested: rows.append(request.url))
            page.on(
                "console",
                lambda message, rows=console_errors: rows.append(message.text)
                if message.type == "error"
                else None,
            )
            page.on("pageerror", lambda error, rows=page_errors: rows.append(str(error)))
            route_case(page, story(count), bootstrap(japanese=japanese), action)
            started = time.perf_counter()
            response = page.goto(f"{base_url}/static/ui-next.html{route_hash}")
            if response is None or not response.ok:
                raise RuntimeError(f"Play failed to load for {case_id}")
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            if count:
                page.wait_for_selector("[data-play-composer]")
                page.wait_for_function(
                    "document.querySelector('[data-play-transcript]')?.dataset.scrollSettled === 'true'"
                )
            render_ms = (time.perf_counter() - started) * 1000
            apply_action(page, action)
            page.wait_for_function("document.fonts.status === 'loaded'")
            page.evaluate(
                "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))))"
            )
            screenshot = SCREENSHOTS / f"{case_id}.png"
            page.screenshot(path=screenshot, animations="disabled")
            results.append(
                {
                    "id": case_id,
                    "viewport": {"width": width, "height": height},
                    "action": action,
                    **inspect_page(page, requested, render_ms),
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "screenshot": screenshot.relative_to(ROOT).as_posix(),
                    "screenshot_sha256": sha256(screenshot),
                }
            )
            page.close()
        browser.close()
    return {
        "schema_version": 1,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_tree_sha256": tree_hash(),
        "browser": f"Chromium {browser_version}",
        "platform": platform.platform(),
        "cases": results,
    }


def main() -> int:
    report = capture()
    target = OUTPUT / "play-report.json"
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Captured {len(report['cases'])} WP-04 Play cases at {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
