"""Capture deterministic WP-16 person-authoring workspace evidence."""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "docs" / "design" / "sonder-ui-replacement" / "wp16" / "screenshots"
)
CASES = (
    ("person-editor-1440.png", 1440, 900),
    ("person-editor-1024.png", 1024, 768),
    ("person-editor-1024x600.png", 1024, 600),
    ("person-editor-390.png", 390, 844),
    ("person-editor-844x390.png", 844, 390),
)

BOOTSTRAP = {
    "ui_language": "en", "ui_direction": "ltr", "ui_messages": {},
    "chats": [{"id": 1, "name": "The Lantern Archive"}],
    "characters": [{"id": 7, "name": "Mara Venn"}],
    "personas": [{"id": 9, "name": "Rin Vale"}],
    "lorebooks": [{"id": 12, "name": "Quiet Roads"}],
    "providers": [], "language_packs": [], "extensions": [],
    "extension_errors": [], "extension_lanes": [],
}

PERSON_DOCUMENT = {
    "identity": {
        "uid": "char_mara", "name": "Mara Venn", "aliases": ["Mara"],
        "pronouns": {"subject": "she", "object": "her", "possessive": "her"},
    },
    "initial_outfit": {
        "wearing": ["rain-dark courier coat", "weathered signal boots"],
        "state": ["rain-damp"], "regions": {"torso": ["rain-dark courier coat"]},
    },
    "simulation": {
        "tier": "mid", "temperature": 0.8, "sampler": {"top_p": 0.9},
        "curiosity": 0.5, "offscreen_agent": False,
    },
    "embodiment": {
        "visible": {"summary": "A careful courier in a rain-dark coat."},
        "senses": ["keen hearing"], "scent": "rain and lamp oil",
        "latent": [], "extra_parts": [],
    },
    "psychology": {
        "traits": ["watchful", "patient"],
        "values": ["keep promises", "protect the signal roads"],
        "drive": {"essence": "Carry the warning through", "taboo": "Abandon a traveler"},
        "coping": {"default": "Count each route marker twice"},
    },
    "social": {
        "voice": {"register": "quiet", "cadence": "measured"},
        "boundaries": ["does not reveal a courier's client"],
    },
    "competence": {"abilities": ["route finding", "signal repair"]},
    "knowledge": {
        "public_history": "A courier trusted along the old signal roads.",
        "private_history": ["Once missed the last lamp at North Ridge."],
    },
    "initial_state": {
        "mood": {"label": "watchful"}, "stress": 0.25,
        "hedonics": {"comfort": 0.15},
    },
    "opening": {
        "first_message": "The rain followed you in.",
        "greetings": [{"prose": "The rain followed you in."}],
    },
    "extension_payload": {"route_marks": ["north", "lantern", "archive"]},
}

ITEM = {
    "kind": "character", "id": 7, "key": "character:7", "name": "Mara Venn",
    "summary": "A careful courier who knows the signal roads.", "subtype": "character",
    "created": 1, "reusable": True, "archived": False, "use_count": 1,
    "associations": [{"story_id": 1, "story_name": "The Lantern Archive", "state": "active"}],
}


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


def fulfill(route: Route, payload: object) -> None:
    route.fulfill(
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def route_api(page: Page) -> None:
    def handler(route: Route) -> None:
        path = route.request.url.split("?", 1)[0]
        if path.endswith("/api/bootstrap"):
            fulfill(route, BOOTSTRAP)
        elif path.endswith("/api/library"):
            fulfill(route, {
                "items": [ITEM],
                "facets": {
                    "types": {"story": 0, "character": 1, "persona": 0, "lore": 0},
                    "scopes": {"all": 1, "story": 1, "unassigned": 0, "multiple": 0},
                },
                "page": {"offset": 0, "limit": 100, "returned": 1, "total": 1},
                "query": {"scope": "all", "sort": "name", "visibility": "active"},
            })
        elif path.endswith("/api/library/authoring/character/7"):
            fulfill(route, {
                "kind": "character", "id": 7, "owner": "character:7",
                "revision": "wp16-evidence", "document": PERSON_DOCUMENT,
            })
        else:
            fulfill(route, {"detail": "Not found"})

    page.route("**/api/**", handler)


def main() -> None:
    from playwright.sync_api import sync_playwright

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for filename, width, height in CASES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.emulate_media(reduced_motion="reduce")
            route_api(page)
            page.goto(
                f"{base_url}/static/ui-next.html"
                "#/library/characters?item=character%3A7&mode=edit"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'"
            )
            page.get_by_role("tab", name="Inner life").click()
            disclosures = page.locator(
                '.ui-person-editor__panel:not([hidden]) details > summary'
            )
            for index in range(disclosures.count()):
                disclosures.nth(index).click()
            page.locator("[data-person-scroll-region]").evaluate(
                "node => { node.scrollTop = 0; }"
            )
            page.evaluate("document.fonts.ready")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            destination = OUTPUT / filename
            page.screenshot(path=destination, full_page=False)
            if destination.stat().st_size == 0:
                raise RuntimeError(f"Empty screenshot: {destination}")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
