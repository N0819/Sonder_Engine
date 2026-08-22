"""Capture deterministic Gate G2 application-shell evidence."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "g2"
SCREENSHOTS = OUTPUT / "screenshots"

BASE_BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}

LONG_JAPANESE = {
    "Play": "プレイ中の物語と現在進行中の場面を確認する場所",
    "Library": "ストーリーと登場人物と世界設定をまとめて探すライブラリ",
    "Settings": "表示や接続やメンテナンスを調整するための設定",
    "Your active story and its tools stay together here.": (
        "現在選ばれている物語と、その物語だけに関係する道具は、"
        "迷わず戻れるようにこの場所へまとめて表示されます。"
    ),
    "Choose a story to begin.": "始めるストーリーをライブラリから選んでください。",
    "Go To": "目的の場所へすばやく移動",
    "Find a destination": "移動したい画面や機能の名前を入力して検索",
}

CASES = (
    ("desktop-wide", 1280, 800, "#/play", "none", BASE_BOOTSTRAP),
    ("desktop-expansive", 1440, 900, "#/library", "none", BASE_BOOTSTRAP),
    ("medium", 1024, 768, "#/settings", "none", BASE_BOOTSTRAP),
    ("tablet", 768, 1024, "#/library/characters", "none", BASE_BOOTSTRAP),
    ("phone", 390, 844, "#/play", "none", BASE_BOOTSTRAP),
    ("narrow-phone", 360, 800, "#/settings/add-ons", "none", BASE_BOOTSTRAP),
    ("landscape", 844, 390, "#/play", "none", BASE_BOOTSTRAP),
    ("short-laptop", 1024, 600, "#/library", "none", BASE_BOOTSTRAP),
    ("zoom-200-equivalent", 640, 360, "#/settings", "none", BASE_BOOTSTRAP),
    (
        "japanese-long-copy",
        390,
        844,
        "#/play",
        "none",
        {**BASE_BOOTSTRAP, "ui_language": "ja", "ui_messages": LONG_JAPANESE},
    ),
    ("accessibility-mode", 390, 844, "#/play", "accessibility", BASE_BOOTSTRAP),
    ("go-to", 1024, 768, "#/play", "go-to", BASE_BOOTSTRAP),
    ("inspector-sheet", 390, 844, "#/play", "inspector", BASE_BOOTSTRAP),
    ("extension-mount", 1024, 768, "#/settings/add-ons", "extension", BASE_BOOTSTRAP),
    ("extension-failure", 1024, 768, "#/settings/add-ons", "extension-failure", BASE_BOOTSTRAP),
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(QuietHandler, directory=str(ROOT)),
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_tree_hash() -> str:
    digest = hashlib.sha256()
    roots = (
        ROOT / "static" / "css" / "ui",
        ROOT / "static" / "js" / "ui-next",
        ROOT / "static" / "js" / "ui" / "components",
    )
    files = [path for base in roots for path in base.rglob("*") if path.is_file()]
    files += [
        ROOT / "static" / "ui-next.html",
        ROOT / "language_packs" / "en" / "ui.json",
        ROOT / "language_packs" / "ja" / "ui.json",
    ]
    for path in sorted(files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fulfill_json(route: Route, payload: dict[str, object], *, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def apply_action(page, action: str) -> None:
    if action == "accessibility":
        page.evaluate(
            """() => {
              const root = document.documentElement;
              root.dataset.a11yHighContrast = "true";
              root.dataset.a11ySolid = "true";
              root.dataset.a11yStrongFocus = "true";
              root.dataset.a11yLargeUi = "true";
              root.dataset.a11yLargeProse = "true";
              root.dataset.a11yRoomyTargets = "true";
              root.dataset.a11yStatusMarkers = "true";
              root.dataset.a11yReducedMotion = "true";
            }"""
        )
    elif action == "go-to":
        page.get_by_role("button", name="Go To", exact=True).click()
        page.get_by_role("searchbox", name="Find a destination").fill("Library")
    elif action == "inspector":
        page.get_by_role("button", name="Open context panel").click()
    elif action in {"extension", "extension-failure"}:
        failure = action == "extension-failure"
        page.evaluate(
            """failure => {
              window.Sonder._begin("evidence-addon");
              window.Sonder.registerView({
                id: failure ? "failed" : "field-notes",
                label: failure ? "Unavailable field notes" : "Field notes",
                render(container) {
                  if (failure) throw new Error("evidence failure");
                  container.textContent = "Contained add-on view mounted through the public adapter.";
                },
              });
              window.Sonder._end();
            }""",
            failure,
        )
        view_id = "failed" if failure else "field-notes"
        page.evaluate(
            """viewId => {
              const params = new URLSearchParams({
                extension: "evidence-addon",
                kind: "legacy-view",
                view: viewId,
              });
              location.hash = `#/settings/add-ons?${params}`;
            }""",
            view_id,
        )
        page.wait_for_selector(
            '[data-extension-owner="evidence-addon"]',
            state="attached",
        )
        if failure:
            page.wait_for_selector('.ui-extension-view [data-state="error"]')


def inspect_page(page, requested: list[str]) -> dict[str, object]:
    metrics = page.evaluate(
        """() => {
          const visible = element => {
            const rect = element.getBoundingClientRect();
            return rect.width > 1 && rect.height > 1
              && rect.bottom > 0 && rect.right > 0
              && rect.top < innerHeight && rect.left < innerWidth;
          };
          const controls = [...document.querySelectorAll('button, input, select, textarea, a[href]')]
            .filter(visible);
          const destinations = [...document.querySelectorAll('[data-core-destination]')]
            .filter(visible);
          const rect = element => element.getBoundingClientRect();
          return {
            state: document.documentElement.dataset.uiNextState,
            ready: document.documentElement.dataset.uiNextReady || null,
            layout_state: document.documentElement.dataset.layoutState,
            language: document.documentElement.lang,
            direction: document.documentElement.dir,
            route: location.hash,
            horizontal_overflow_px:
              document.documentElement.scrollWidth - document.documentElement.clientWidth,
            minimum_visible_target_px: controls.length
              ? Math.min(...controls.map(element => Math.min(rect(element).width, rect(element).height)))
              : null,
            minimum_destination_target_px: destinations.length
              ? Math.min(...destinations.map(element => Math.min(rect(element).width, rect(element).height)))
              : null,
            destinations: destinations.map(element => element.dataset.coreDestination),
            landmarks: {
              navigation: document.querySelectorAll('nav').length,
              main: document.querySelectorAll('main').length,
              complementary: [...document.querySelectorAll('aside')].filter(visible).length,
              dialog: [...document.querySelectorAll('[role="dialog"]')].filter(visible).length,
            },
            focus_identity: document.activeElement?.dataset?.focusIdentity
              || document.activeElement?.getAttribute('aria-label')
              || document.activeElement?.tagName?.toLowerCase()
              || null,
            classic_global: Object.hasOwn(window, 'S'),
            adapter_global: Object.hasOwn(window, 'Sonder'),
            sensitive_text: /password|api[_ -]?key|join code|cookie|session=/i.test(document.body.textContent),
            extension_surface: document.querySelector('[data-extension-owner]')?.textContent || null,
            unavailable_surface: document.querySelector('.ui-extension-view [data-state="error"]')?.textContent || null,
            resources: performance.getEntriesByType('resource')
              .map(entry => new URL(entry.name).pathname)
              .sort(),
          };
        }"""
    )
    api_paths = sorted(
        urlparse(url).path
        for url in requested
        if urlparse(url).path.startswith("/api/")
    )
    metrics["api_requests"] = api_paths
    metrics["bootstrap_request_count"] = api_paths.count("/api/bootstrap")
    for key in ("minimum_visible_target_px", "minimum_destination_target_px"):
        if metrics[key] is not None:
            metrics[key] = round(metrics[key], 2)
    return metrics


def capture() -> dict[str, object]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    results: list[dict[str, object]] = []

    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        browser_version = browser.version
        for case_id, width, height, route_hash, action, bootstrap in CASES:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page.emulate_media(reduced_motion="reduce")
            console_errors: list[str] = []
            page_errors: list[str] = []
            requested: list[str] = []
            page.on("console", lambda message, rows=console_errors: rows.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error, rows=page_errors: rows.append(str(error)))
            page.on("request", lambda request, rows=requested: rows.append(request.url))
            page.route(
                "**/api/bootstrap",
                lambda route, _request, data=bootstrap: fulfill_json(route, data),
            )
            response = page.goto(f"{base_url}/static/ui-next.html{route_hash}")
            if response is None or not response.ok:
                raise RuntimeError(f"Application shell failed to load for {case_id}")
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            apply_action(page, action)
            page.wait_for_timeout(0)
            screenshot = SCREENSHOTS / f"{case_id}.png"
            page.screenshot(path=screenshot, full_page=True, animations="disabled")
            results.append({
                "id": case_id,
                "viewport": {"width": width, "height": height},
                "action": action,
                **inspect_page(page, requested),
                "console_errors": console_errors,
                "page_errors": page_errors,
                "screenshot": screenshot.relative_to(ROOT).as_posix(),
                "screenshot_sha256": sha256(screenshot),
            })
            page.close()

        page = browser.new_page(viewport={"width": 1024, "height": 768})
        page.route(
            "**/api/bootstrap",
            lambda route: fulfill_json(route, {"detail": "Expired"}, status=401),
        )
        page.goto(f"{base_url}/static/ui-next-lab.html")
        session_expiry = page.evaluate(
            """async (base) => {
              const { bootRuntime } = await import(
                `${base}/static/js/ui-next/bootstrap.js?release=wp04.1`
              );
              const destinations = [];
              let kind = null;
              try {
                await bootRuntime({
                  host: true,
                  root: document.documentElement,
                  target: window,
                  onLoginRequired: destination => destinations.push(destination),
                });
              } catch (error) {
                kind = error.kind;
              }
              return {
                kind,
                destinations,
                state: document.documentElement.dataset.uiNextState,
                ready: document.documentElement.dataset.uiNextReady || null,
                classic_global: Object.hasOwn(window, 'S'),
                adapter_global: Object.hasOwn(window, 'Sonder'),
              };
            }""",
            base_url,
        )
        results.append({"id": "session-expiry", **session_expiry})
        page.close()
        browser.close()

    return {
        "schema_version": 1,
        "source_commit": source_commit,
        "source_tree_sha256": source_tree_hash(),
        "browser": f"Chromium {browser_version}",
        "platform": platform.platform(),
        "cases": results,
    }


def main() -> int:
    report = capture()
    target = OUTPUT / "shell-report.json"
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Captured {len(report['cases'])} G2 cases at {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
