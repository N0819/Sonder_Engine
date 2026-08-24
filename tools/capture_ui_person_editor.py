"""Capture deterministic WP-16 person-authoring workspace evidence."""

from __future__ import annotations

import argparse
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
    {"filename": "person-editor-1440.png", "width": 1440, "height": 900, "section": "Inner life"},
    {"filename": "person-editor-1024.png", "width": 1024, "height": 768, "section": "Inner life"},
    {"filename": "person-editor-1024x600.png", "width": 1024, "height": 600, "section": "Inner life"},
    {"filename": "person-editor-390.png", "width": 390, "height": 844, "section": "Inner life"},
    {"filename": "person-editor-360.png", "width": 360, "height": 800, "section": "Inner life"},
    {"filename": "person-editor-844x390.png", "width": 844, "height": 390, "section": "Inner life"},
    {"filename": "persona-editor-1440.png", "width": 1440, "height": 900, "kind": "persona", "section": "Story presence"},
    {"filename": "story-character-editor-1440.png", "width": 1440, "height": 900, "mode": "story-card", "section": "Inner life"},
    {"filename": "person-editor-discard-1440.png", "width": 1440, "height": 900, "state": "discard"},
    {"filename": "person-editor-invalid-1440.png", "width": 1440, "height": 900, "state": "invalid"},
    {"filename": "person-editor-ja-390.png", "width": 390, "height": 844, "language": "ja", "section": "Simulation"},
    {"filename": "person-editor-accessibility-1440.png", "width": 1440, "height": 900, "accessibility": True, "section": "Appearance"},
    {"filename": "person-editor-zoom-200.png", "width": 720, "height": 450, "section": "Inner life"},
)

SECTION_IDS = {
    "Basics": "basics",
    "Appearance": "appearance",
    "History": "history",
    "Inner life": "inner-life",
    "Opening": "opening",
    "Simulation": "simulation",
    "Story presence": "story-presence",
}

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

PERSONA_DOCUMENT = {
    "identity": {
        "uid": "persona_rin", "name": "Rin Vale", "aliases": ["Rin"],
        "pronouns": {"subject": "they", "object": "them", "possessive": "their"},
    },
    "initial_outfit": {"wearing": ["blue traveling coat"], "state": [], "regions": {}},
    "embodiment": {
        "visible": {"summary": "A calm traveler with an ink-stained cuff."},
        "senses": [], "scent": "cedar", "latent": [], "extra_parts": [],
    },
    "competence": {"abilities": ["patient listening", "map reading"]},
    "knowledge": {
        "public_history": "A traveler returning to the Lantern Archive.",
        "private_history": ["Knows why the northern signal failed."],
    },
    "narration": {"voice_setting": "Close third person with restrained sensory detail."},
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


def route_api(page: Page, case: dict[str, object]) -> list[str]:
    kind = str(case.get("kind") or "character")
    language = str(case.get("language") or "en")
    messages = (
        json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text(encoding="utf-8"))
        if language == "ja" else {}
    )
    seen: list[str] = []

    def handler(route: Route) -> None:
        path = route.request.url.split("?", 1)[0]
        seen.append(path)
        if path.endswith("/api/bootstrap"):
            fulfill(route, {**BOOTSTRAP, "ui_language": language, "ui_messages": messages})
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
        elif path.endswith("/api/library/authoring/persona/9"):
            fulfill(route, {
                "kind": "persona", "id": 9, "owner": "persona:9",
                "revision": "wp16-persona-evidence", "document": PERSONA_DOCUMENT,
            })
        elif path.endswith("/api/chats/1"):
            fulfill(route, {
                "chat": {"id": 1, "name": "The Lantern Archive"},
                "participants": [{
                    "id": 7, "name": "Mara Venn", "card_source": "library",
                    "sheet": json.dumps(PERSON_DOCUMENT, ensure_ascii=False),
                }],
            })
        else:
            fulfill(route, {"detail": "Not found"})

    page.route("**/api/**", handler)
    return seen


def main() -> None:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="", help="Capture one exact output filename")
    args = parser.parse_args()
    selected = [case for case in CASES if not args.case or case["filename"] == args.case]
    if not selected:
        raise SystemExit(f"Unknown capture case: {args.case}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for case in selected:
            filename = str(case["filename"])
            width = int(case["width"])
            height = int(case["height"])
            page = browser.new_page(viewport={"width": width, "height": height})
            page.emulate_media(reduced_motion="reduce")
            seen_api = route_api(page, case)
            kind = str(case.get("kind") or "character")
            mode = str(case.get("mode") or "edit")
            item = "persona%3A9" if kind == "persona" else "character%3A7"
            story = "&story=1" if mode == "story-card" else ""
            page.goto(
                f"{base_url}/static/ui-next.html"
                f"#/library/{'personas' if kind == 'persona' else 'characters'}"
                f"?item={item}&mode={mode}{story}"
            )
            page.wait_for_function(
                "document.documentElement.dataset.uiNextState === 'ready'",
                timeout=10_000,
            )
            try:
                page.locator(".ui-person-editor").wait_for(state="visible", timeout=10_000)
            except Exception as exc:
                summary = " ".join(page.locator("body").inner_text().split())[:800]
                raise RuntimeError(
                    f"Person editor did not render for {filename}; APIs={seen_api}; body={summary}"
                ) from exc
            if case.get("accessibility"):
                page.locator("html").evaluate(
                    "node => { node.dataset.a11ySolid = 'true'; node.dataset.a11yContrast = 'high'; }"
                )
            state = str(case.get("state") or "")
            if state == "discard":
                page.get_by_role("textbox", name="Name").fill("Mara Venn — revised")
                page.get_by_role("button", name="Discard draft").click()
            elif state == "invalid":
                more = page.locator(".ui-person-editor__more")
                more.locator("summary").click()
                more.get_by_role("button", name="Advanced", exact=True).click()
                page.locator('[name="advanced_json"]').fill("{ not valid JSON")
                page.get_by_role("button", name="Apply advanced JSON").click()
            else:
                section = str(case.get("section") or "Basics")
                page.locator(
                    f'.ui-person-editor__tab[aria-controls$="-{SECTION_IDS[section]}"]'
                ).click()
            page.locator("[data-person-scroll-region]").evaluate(
                "node => { node.scrollTop = 0; }"
            )
            page.evaluate("document.fonts.ready")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            destination = OUTPUT / filename
            page.screenshot(path=destination, full_page=False)
            if destination.stat().st_size == 0:
                raise RuntimeError(f"Empty screenshot: {destination}")
            print(f"Captured {filename}")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
