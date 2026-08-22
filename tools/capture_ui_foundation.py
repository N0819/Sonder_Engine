"""Capture deterministic Gate G1 component-laboratory evidence."""

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

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "g1"
SCREENSHOTS = OUTPUT / "screenshots"

CASES = (
    ("theme-carbon", 1440, 900, "carbon-signal", ()),
    ("theme-ash", 1440, 900, "ash-brass", ()),
    ("theme-midnight", 1440, 900, "midnight-ink", ()),
    ("theme-parchment", 1440, 900, "parchment-night", ()),
    ("solid-surfaces", 1024, 768, "carbon-signal", ("solid-surfaces",)),
    ("reduced-motion", 1024, 768, "carbon-signal", ("reduced-motion",)),
    ("accessibility-mode", 1024, 768, "carbon-signal", ("accessibility-mode",)),
    ("large-ui-prose", 1024, 768, "carbon-signal", ("large-ui", "large-prose")),
    ("high-contrast", 1024, 768, "carbon-signal", ("high-contrast",)),
    ("tablet-long-copy", 1024, 768, "carbon-signal", ("long-copy",)),
    ("mobile", 390, 844, "carbon-signal", ("long-copy",)),
    ("narrow", 360, 640, "carbon-signal", ("accessibility-mode", "long-copy")),
    ("zoom-200-equivalent", 640, 360, "carbon-signal", ("long-copy",)),
    ("landscape", 844, 390, "midnight-ink", ("long-copy",)),
    ("desktop", 1440, 900, "carbon-signal", ("long-copy",)),
)


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
    roots = (ROOT / "static" / "css" / "ui", ROOT / "static" / "js" / "ui")
    files = [path for base in roots for path in base.rglob("*") if path.is_file()]
    files += [ROOT / "static" / "ui-next.html", ROOT / "static" / "ui-next-lab.html"]
    for path in sorted(files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def apply_preferences(page, preferences: tuple[str, ...]) -> None:
    labels = {
        "solid-surfaces": "Solid surfaces",
        "accessibility-mode": "Accessibility Mode",
        "large-ui": "Larger interface",
        "large-prose": "Larger story text",
        "high-contrast": "High contrast",
    }
    for preference in preferences:
        if preference in labels:
            page.get_by_label(labels[preference]).check()


def capture() -> dict[str, object]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    results: list[dict[str, object]] = []

    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        browser_version = browser.version
        for case_id, width, height, theme, preferences in CASES:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            console_errors: list[str] = []
            page_errors: list[str] = []
            api_requests = 0
            page.on("console", lambda message, errors=console_errors: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error, errors=page_errors: errors.append(str(error)))

            def count_api(request) -> None:
                nonlocal api_requests
                if urlparse(request.url).path.startswith("/api/"):
                    api_requests += 1

            page.on("request", count_api)
            if "reduced-motion" in preferences:
                page.emulate_media(reduced_motion="reduce")
            response = page.goto(f"{base_url}/static/ui-next-lab.html")
            if response is None or not response.ok:
                raise RuntimeError(f"Lab failed to load for {case_id}")
            page.locator("html[data-ui-next-ready='true']").wait_for()
            page.locator(f'[data-theme-choice="{theme}"]').click()
            apply_preferences(page, preferences)
            page.evaluate("scrollTo(0, 0)")
            screenshot = SCREENSHOTS / f"{case_id}.png"
            page.screenshot(path=screenshot, full_page=True, animations="disabled")
            metrics = page.evaluate("""() => {
              const visible = [...document.querySelectorAll('button, input, select, textarea')]
                .filter(element => { const rect = element.getBoundingClientRect(); return rect.width > 1 && rect.height > 1; })
                .map(element => Math.min(element.getBoundingClientRect().width, element.getBoundingClientRect().height));
              const style = getComputedStyle(document.documentElement);
              return {
                overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                minimumTarget: Math.min(...visible),
                canvas: style.getPropertyValue('--ui-color-canvas').trim(),
                text: style.getPropertyValue('--ui-color-text').trim(),
              };
            }""")
            results.append({
                "id": case_id,
                "theme": theme,
                "viewport": {"width": width, "height": height},
                "preferences": list(preferences),
                "horizontal_overflow_px": metrics["overflow"],
                "minimum_target_px": round(metrics["minimumTarget"], 2),
                "semantic_colors": {"canvas": metrics["canvas"], "text": metrics["text"]},
                "console_errors": console_errors,
                "page_errors": page_errors,
                "api_requests": api_requests,
                "screenshot": screenshot.relative_to(ROOT).as_posix(),
                "screenshot_sha256": sha256(screenshot),
            })
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
    target = OUTPUT / "foundation-report.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Captured {len(report['cases'])} G1 cases at {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
