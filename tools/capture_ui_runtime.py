"""Capture deterministic WP-02 runtime-boundary evidence."""

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

from playwright.sync_api import Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp02"
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


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
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
    roots = (ROOT / "static" / "css" / "ui", ROOT / "static" / "js" / "ui-next")
    files = [path for base in roots for path in base.rglob("*") if path.is_file()]
    files += [ROOT / "static" / "ui-next-runtime.html"]
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


def inspect_page(page) -> dict[str, object]:
    return page.evaluate(
        """() => {
          const controls = [...document.querySelectorAll('button, input, select, textarea, a')]
            .filter(element => {
              const rect = element.getBoundingClientRect();
              return rect.width > 1 && rect.height > 1;
            });
          const targetSize = element => {
            const target = element.matches('input[type="checkbox"], input[type="radio"]')
              ? element.closest('label') || element
              : element;
            const rect = target.getBoundingClientRect();
            return Math.min(rect.width, rect.height);
          };
          return {
            state: document.documentElement.dataset.uiNextState,
            ready: document.documentElement.dataset.uiNextReady || null,
            language: document.documentElement.lang,
            direction: document.documentElement.dir,
            status: document.querySelector('[data-runtime-status]')?.textContent,
            detail: document.querySelector('[data-runtime-detail]')?.textContent,
            horizontal_overflow_px:
              document.documentElement.scrollWidth - document.documentElement.clientWidth,
            minimum_target_px: controls.length ? Math.min(...controls.map(targetSize)) : null,
            focus: document.activeElement?.getAttribute('data-runtime-diagnostics') !== null
              ? 'diagnostics-toggle'
              : document.activeElement?.tagName?.toLowerCase() || null,
            classic_global: Object.hasOwn(window, 'S'),
            adapter_global: Object.hasOwn(window, 'Sonder'),
          };
        }"""
    )


def capture() -> dict[str, object]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    results: list[dict[str, object]] = []

    visual_cases = (
        ("desktop", 1440, 900, BASE_BOOTSTRAP, False, False),
        ("mobile", 390, 844, BASE_BOOTSTRAP, False, False),
        ("zoom-200-equivalent", 640, 360, BASE_BOOTSTRAP, False, False),
        ("keyboard", 1024, 768, BASE_BOOTSTRAP, True, False),
        (
            "japanese-long-copy",
            390,
            844,
            {
                **BASE_BOOTSTRAP,
                "ui_language": "ja",
                "ui_messages": {
                    "Authenticated development fixture · WP02": "認証済み開発用ランタイム境界検証フィクスチャ · WP02",
                    "Runtime boundary": "ランタイムサービス境界の検証",
                    "Loading runtime services…": "ランタイムサービスを安全に読み込んでいます…",
                    "The replacement service graph has not finished booting.": "置換インターフェースのサービス構成は、まだ起動を完了していません。",
                    "Show redacted diagnostics": "機密情報を除去した診断記録を表示",
                    "This verifies native runtime boundaries only. The replacement Play, Library, and Settings shell begins in WP03.": "ここではネイティブランタイム境界だけを検証します。Play、Library、Settings の置換シェルは WP03 から始まります。",
                    "Back to replacement entry": "置換インターフェース入口へ戻る",
                    "Runtime services ready": "ランタイムサービスの準備ができました",
                },
            },
            False,
            False,
        ),
        (
            "extension-failure",
            1024,
            768,
            {
                **BASE_BOOTSTRAP,
                "extensions": [{
                    "id": "broken-ui",
                    "enabled": True,
                    "capabilities": {"ui": {"js": "ui.js"}},
                }],
            },
            False,
            True,
        ),
    )

    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        browser_version = browser.version
        for case_id, width, height, bootstrap, keyboard, extension_failure in visual_cases:
            page = browser.new_page(viewport={"width": width, "height": height})
            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("console", lambda message, rows=console_errors: rows.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error, rows=page_errors: rows.append(str(error)))
            page.route(
                "**/api/bootstrap",
                lambda route, _request, data=bootstrap: fulfill_json(route, data),
            )
            if extension_failure:
                page.route("**/api/extensions/broken-ui/ui.js", lambda route: route.abort())
            response = page.goto(f"{base_url}/static/ui-next-runtime.html")
            if response is None or not response.ok:
                raise RuntimeError(f"Runtime harness failed to load for {case_id}")
            page.wait_for_function(
                "['ready', 'failed'].includes(document.documentElement.dataset.uiNextState)"
            )
            if keyboard:
                page.keyboard.press("Tab")
            if extension_failure:
                page.get_by_label("Show redacted diagnostics").check()
            screenshot = SCREENSHOTS / f"{case_id}.png"
            page.screenshot(path=screenshot, full_page=True, animations="disabled")
            metrics = inspect_page(page)
            metrics["minimum_target_px"] = round(metrics["minimum_target_px"], 2)
            results.append({
                "id": case_id,
                "viewport": {"width": width, "height": height},
                **metrics,
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
                `${base}/static/js/ui-next/bootstrap.js?release=wp02.1`
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
    target = OUTPUT / "runtime-report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Captured {len(report['cases'])} WP-02 cases at {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
