"""Capture deterministic WP-06 Library replacement evidence."""

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
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "g4" / "library"
SCREENSHOTS = OUTPUT / "screenshots"

# id, width, height, hash, data mode, action, language, motion
CASES = (
    ("expansive-all", 1600, 900, "#/library", "normal", "", "en", "system"),
    ("wide-current-story", 1440, 900, "#/library?scope=story&story=1", "normal", "", "en", "system"),
    ("desktop-choose-story", 1280, 820, "#/library", "normal", "", "en", "system"),
    ("desktop-unassigned", 1280, 820, "#/library?scope=unassigned", "normal", "", "en", "system"),
    ("desktop-multiple", 1280, 820, "#/library?scope=multiple", "normal", "", "en", "system"),
    ("desktop-stories", 1280, 820, "#/library/stories", "normal", "", "en", "system"),
    ("desktop-characters", 1280, 820, "#/library/characters", "normal", "", "en", "system"),
    ("desktop-personas", 1280, 820, "#/library/personas", "normal", "", "en", "system"),
    ("desktop-lore", 1280, 820, "#/library/lore", "normal", "", "en", "system"),
    ("desktop-search", 1280, 820, "#/library?q=Quiet", "normal", "", "en", "system"),
    ("desktop-no-results", 1280, 820, "#/library?q=No+such+item", "normal", "", "en", "system"),
    ("desktop-story-detail", 1280, 820, "#/library/stories?item=story%3A1", "normal", "", "en", "system"),
    ("desktop-associations", 1280, 820, "#/library/characters?item=character%3A7", "normal", "", "en", "system"),
    ("desktop-archived", 1280, 820, "#/library/characters?visibility=archived&item=character%3A99", "normal", "", "en", "system"),
    ("desktop-restore", 1280, 820, "#/library/characters?visibility=archived&item=character%3A99", "normal", "restore", "en", "system"),
    ("desktop-empty", 1280, 820, "#/library", "empty", "", "en", "system"),
    ("desktop-unavailable", 1280, 820, "#/library/characters?item=character%3A404", "normal", "", "en", "system"),
    ("desktop-loading", 1280, 820, "#/library", "loading", "", "en", "system"),
    ("desktop-offline", 1280, 820, "#/library", "offline", "", "en", "system"),
    ("desktop-error", 1280, 820, "#/library", "error", "", "en", "system"),
    ("medium-lore-detail", 1024, 768, "#/library/lore?item=lore%3A12", "normal", "", "en", "system"),
    ("tablet-associations", 768, 1024, "#/library/characters?item=character%3A7", "normal", "", "en", "system"),
    ("phone-430-all", 430, 860, "#/library", "normal", "", "en", "system"),
    ("phone-390-detail", 390, 844, "#/library/lore?item=lore%3A12", "normal", "", "en", "system"),
    ("phone-360-multiple", 360, 800, "#/library?scope=multiple", "normal", "", "en", "system"),
    ("phone-back-context", 390, 844, "#/library/characters", "scale", "back", "en", "system"),
    ("short-landscape", 844, 390, "#/library/characters?item=character%3A7", "normal", "", "en", "system"),
    ("short-desktop", 1280, 560, "#/library", "normal", "", "en", "system"),
    ("zoom-200-equivalent", 640, 450, "#/library/personas?item=persona%3A9", "normal", "", "en", "system"),
    ("japanese-phone", 390, 844, "#/library/characters?item=character%3A7", "normal", "", "ja", "system"),
    ("reduced-motion", 1280, 820, "#/library/lore", "normal", "", "en", "reduce"),
    ("scale-1000", 1280, 820, "#/library/characters", "scale", "", "en", "system"),
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_root():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)),
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


def fulfill(route: Route, payload: object, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash() -> str:
    digest = hashlib.sha256()
    roots = (ROOT / "static" / "css" / "ui", ROOT / "static" / "js" / "ui-next")
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


def bootstrap(language: str) -> dict:
    messages = (
        json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text(encoding="utf-8"))
        if language == "ja" else {}
    )
    return {
        "ui_language": language,
        "ui_direction": "ltr",
        "ui_messages": messages,
        "chats": [
            {"id": 1, "name": "The Lantern Archive"},
            {"id": 2, "name": "The Quiet Signal"},
        ],
        "characters": [], "personas": [], "lorebooks": [], "providers": [],
        "language_packs": [], "extensions": [], "extension_errors": [],
        "extension_lanes": [],
    }


def association(story_id: int, story_name: str, state: str, **extra: object) -> dict:
    return {"story_id": story_id, "story_name": story_name, "state": state, **extra}


def normal_items(archive_state: dict[str, bool]) -> list[dict]:
    story_a = "The Lantern Archive"
    story_b = "The Quiet Signal"
    return [
        {"kind": "story", "id": 1, "key": "story:1", "name": story_a,
         "summary": "A city keeps its light through the long rain.", "subtype": "",
         "created": 100.0, "reusable": False, "archived": False,
         "use_count": 0, "associations": []},
        {"kind": "story", "id": 2, "key": "story:2", "name": story_b,
         "summary": "An old relay wakes beyond the ridge.", "subtype": "",
         "created": 110.0, "reusable": False, "archived": False,
         "use_count": 0, "associations": []},
        {"kind": "character", "id": 7, "key": "character:7", "name": "Mara Venn",
         "summary": "A careful courier who knows the signal roads.", "subtype": "",
         "created": 90.0, "reusable": True, "archived": False, "use_count": 2,
         "associations": [association(1, story_a, "active"), association(2, story_b, "dormant")]},
        {"kind": "character", "id": 8, "key": "character:8", "name": "Ivo Senn",
         "summary": "A patient lampwright.", "subtype": "", "created": 91.0,
         "reusable": True, "archived": False, "use_count": 0, "associations": []},
        {"kind": "character", "id": 99, "key": "character:99", "name": "Archived Wayfinder",
         "summary": "Kept out of ordinary Library views.", "subtype": "", "created": 80.0,
         "reusable": True, "archived": archive_state["character:99"],
         "use_count": 0, "associations": []},
        {"kind": "persona", "id": 9, "key": "persona:9", "name": "Rin Vale",
         "summary": "The primary player in the Lantern Archive.", "subtype": "",
         "created": None, "reusable": True, "archived": False, "use_count": 1,
         "associations": [association(1, story_a, "primary")]},
        {"kind": "persona", "id": 10, "key": "persona:10", "name": "Tala",
         "summary": "A reusable player persona.", "subtype": "", "created": None,
         "reusable": True, "archived": False, "use_count": 0, "associations": []},
        {"kind": "lore", "id": 12, "key": "lore:12", "name": "Quiet Roads",
         "summary": "Paths between old signal towers.", "subtype": "setting",
         "created": None, "reusable": True, "archived": False, "use_count": 2,
         "associations": [association(1, story_a, "attached", story_item_id=212),
                          association(2, story_b, "canon", story_item_id=312)]},
        {"kind": "lore", "id": 13, "key": "lore:13", "name": "Lamp Rites",
         "summary": "Customs of the city lamps.", "subtype": "culture", "created": None,
         "reusable": True, "archived": False, "use_count": 0, "associations": []},
    ]


def scale_items() -> list[dict]:
    return [
        {"kind": "character", "id": index, "key": f"character:{index}",
         "name": f"Library Character {index:04d}",
         "summary": "A deterministic scale fixture.", "subtype": "",
         "created": float(index), "reusable": True, "archived": False,
         "use_count": 0, "associations": []}
        for index in range(1, 1001)
    ]


def belongs(item: dict, story_id: int) -> bool:
    return (
        item["kind"] == "story" and item["id"] == story_id
    ) or any(row["story_id"] == story_id for row in item["associations"])


def project(items: list[dict], query: dict[str, list[str]]) -> dict:
    visibility = query.get("visibility", ["active"])[0]
    selected_type = query.get("types", [""])[0]
    scope = query.get("scope", ["all"])[0]
    story_id = int(query.get("story_id", ["0"])[0] or 0)
    needle = query.get("q", [""])[0].strip().casefold()
    selected = [
        row for row in items
        if bool(row["archived"]) == (visibility == "archived")
        and (not selected_type or row["kind"] == selected_type)
        and (not needle or needle in json.dumps(row, ensure_ascii=False).casefold())
    ]
    scope_facets = {
        "all": len(selected),
        "story": sum(1 for row in selected if belongs(row, story_id)) if story_id else None,
        "unassigned": sum(1 for row in selected if row["reusable"] and row["use_count"] == 0),
        "multiple": sum(1 for row in selected if row["reusable"] and row["use_count"] > 1),
    }
    if scope == "story":
        selected = [row for row in selected if belongs(row, story_id)]
    elif scope == "unassigned":
        selected = [row for row in selected if row["reusable"] and row["use_count"] == 0]
    elif scope == "multiple":
        selected = [row for row in selected if row["reusable"] and row["use_count"] > 1]
    selected.sort(key=lambda row: (row["name"].casefold(), row["kind"], row["id"]))
    total = len(selected)
    page = selected[:100]
    facets = {
        kind: sum(1 for row in selected if row["kind"] == kind)
        for kind in ("story", "character", "persona", "lore")
    }
    return {
        "items": page,
        "facets": {"types": facets, "scopes": scope_facets},
        "page": {"offset": 0, "limit": 100, "returned": len(page), "total": total},
        "query": {"scope": scope, "story_id": story_id or None, "types": [selected_type] if selected_type else [],
                  "q": query.get("q", [""])[0], "sort": "name", "visibility": visibility},
    }


def route_case(page: Page, mode: str, language: str) -> dict:
    observed = {"requests": [], "projection_totals": []}
    archive_state = {"character:99": True}
    items = [] if mode == "empty" else (scale_items() if mode == "scale" else normal_items(archive_state))
    page.on("request", lambda request: observed["requests"].append(request.url))

    def handler(route: Route) -> None:
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        if path == "/api/bootstrap":
            fulfill(route, bootstrap(language))
            return
        if path == "/api/library":
            if mode == "offline":
                route.abort("failed")
                return
            if mode == "error":
                fulfill(route, {"detail": "Library unavailable"}, 503)
                return
            payload = project(items, parse_qs(parsed.query))
            observed["projection_totals"].append(payload["page"]["total"])
            fulfill(route, payload)
            return
        if path == "/api/library/character/99/archive":
            archive_state["character:99"] = request.method == "PUT"
            for row in items:
                if row["key"] == "character:99":
                    row["archived"] = archive_state["character:99"]
            fulfill(route, {"key": "character:99", "archived": archive_state["character:99"], "changed": True})
            return
        if request.method in {"POST", "PUT", "DELETE"}:
            fulfill(route, {"ok": True})
            return
        fulfill(route, {"detail": path}, 404)

    page.route("**/api/**", handler)
    return observed


def wait_for_case(page: Page, mode: str) -> None:
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    expected = {"loading": "loading", "offline": "offline", "error": "error"}.get(mode)
    if expected:
        page.locator(f'[data-state="{expected}"]').wait_for()
    else:
        page.wait_for_function(
            "document.querySelector('[data-library-ledger]') || document.querySelector('.ui-empty')"
        )


def apply_action(page: Page, action: str) -> bool | None:
    if action == "restore":
        page.get_by_role("button", name="Restore character").click()
        page.get_by_role("button", name="Undo").wait_for()
        page.wait_for_function("document.querySelectorAll('[data-library-item]').length === 0")
        return None
    if action == "back":
        before = page.locator("[data-library-item]").count()
        row = page.locator("[data-library-item]").nth(35)
        row.scroll_into_view_if_needed()
        row.click()
        page.get_by_role("dialog", name="Library details").wait_for()
        page.go_back()
        page.get_by_role("dialog", name="Library details").wait_for(state="hidden")
        return before == page.locator("[data-library-item]").count() and before == 100
    return None


def inspect(page: Page, observed: dict, back_context_retained: bool | None) -> dict:
    metrics = page.evaluate("""() => {
      const visible = node => { const r = node.getBoundingClientRect(); return r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
      const controls = [...document.querySelectorAll('button,input,select,textarea,a[href]')].filter(visible);
      const effective = node => node.matches('input,select,textarea') && node.closest('label') ? node.closest('label').getBoundingClientRect() : node.getBoundingClientRect();
      const targets = controls.map(node => { const r = effective(node); return { label: node.getAttribute('aria-label') || node.textContent.trim(), width: Math.round(r.width * 100) / 100, height: Math.round(r.height * 100) / 100 }; });
      const state = document.querySelector('.ui-library__content > .ui-empty')?.dataset.state || null;
      const libraryContent = document.querySelector('.ui-library__content');
      const details = [...document.querySelectorAll('[data-library-detail-host]')];
      const detailContents = details
        .map(detail => detail.querySelector('.ui-library-detail, .ui-empty'))
        .filter(Boolean);
      const visibleDetail = detailContents.find(visible) || null;
      return {
        ui_state: document.documentElement.dataset.uiNextState,
        layout_state: document.documentElement.dataset.layoutState,
        route: location.hash,
        horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
        library_horizontal_overflow_px: libraryContent
          ? Math.max(0, libraryContent.scrollWidth - libraryContent.clientWidth) : 0,
        undersized_compact_targets: document.documentElement.dataset.layoutState === 'compact' ? targets.filter(row => Math.min(row.width, row.height) < 44) : [],
        rendered_rows: document.querySelectorAll('[data-library-item]').length,
        bounded_rows: document.querySelectorAll('[data-library-item]').length <= 100,
        dom_count: document.querySelectorAll('*').length,
        result_state: state,
        detail_visible: Boolean(visibleDetail),
        detail_state: visibleDetail?.dataset.state || null,
        selected_name: (visibleDetail || detailContents[0])?.querySelector('h3')?.textContent || null,
        classic_global: Object.hasOwn(window, 'S'),
        sensitive_text: /api[_ -]?key|join code|cookie|session=/i.test(document.body.textContent),
      };
    }""")
    metrics["api_requests"] = sorted(
        urlparse(url).path for url in observed["requests"] if "/api/" in urlparse(url).path
    )
    metrics["projection_totals"] = observed["projection_totals"]
    metrics["back_context_retained"] = back_context_retained
    return metrics


def capture() -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    results = []
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        browser_version = browser.version
        for case_id, width, height, route_hash, mode, action, language, motion in CASES:
            print(f"Capturing {case_id}…", flush=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.emulate_media(reduced_motion="reduce" if motion == "reduce" else "no-preference")
            if mode in {"loading", "offline", "error"}:
                page.add_init_script(f"""(() => {{
                  const nativeFetch = globalThis.fetch.bind(globalThis);
                  globalThis.fetch = (input, init) => {{
                    if (!String(input).includes('/api/library?')) return nativeFetch(input, init);
                    if ({json.dumps(mode)} === 'loading') return new Promise(() => {{}});
                    if ({json.dumps(mode)} === 'offline') return Promise.reject(new TypeError('Failed to fetch'));
                    return Promise.resolve(new Response(JSON.stringify({{detail:'Library unavailable'}}), {{
                      status: 503, headers: {{'Content-Type': 'application/json'}},
                    }}));
                  }};
                }})();""")
            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("console", lambda message, rows=console_errors: rows.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error, rows=page_errors: rows.append(str(error)))
            observed = route_case(page, mode, language)
            response = page.goto(f"{base_url}/static/ui-next.html{route_hash}")
            if response is None or not response.ok:
                raise RuntimeError(f"Library failed to load for {case_id}")
            wait_for_case(page, mode)
            back_context_retained = apply_action(page, action)
            page.wait_for_function("document.fonts.status === 'loaded'")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            screenshot = SCREENSHOTS / f"{case_id}.png"
            page.screenshot(path=screenshot, animations="disabled")
            results.append({
                "id": case_id,
                "viewport": {"width": width, "height": height},
                "mode": mode, "action": action, "language": language, "motion": motion,
                **inspect(page, observed, back_context_retained),
                "console_errors": console_errors,
                "page_errors": page_errors,
                "screenshot": screenshot.relative_to(ROOT).as_posix(),
                "screenshot_sha256": sha256(screenshot),
            })
            page.close()
        browser.close()
    return {
        "schema_version": 1,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip(),
        "source_tree_sha256": tree_hash(),
        "browser": f"Chromium {browser_version}",
        "platform": platform.platform(),
        "cases": results,
    }


def main() -> None:
    report = capture()
    output = OUTPUT / "library-report.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(report['cases'])} cases to {output}")


if __name__ == "__main__":
    main()
