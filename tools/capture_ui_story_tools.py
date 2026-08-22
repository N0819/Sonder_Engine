"""Capture deterministic WP-05 Story Tools and atmosphere evidence."""

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

from playwright.sync_api import Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "g3" / "story-tools"
SCREENSHOTS = OUTPUT / "screenshots"

TOOLS = ("cast", "world", "style", "dialogue", "attire", "backdrops", "ambience", "conditions", "frames", "multiplayer")
CASES = (
    *((f"desktop-{tool}", 1280, 820, tool, "system", False) for tool in TOOLS),
    ("expansive-cast", 1600, 900, "cast", "system", False),
    ("medium-frames", 1024, 768, "frames", "system", False),
    ("tablet-conditions", 768, 1024, "conditions", "system", False),
    ("phone-world", 390, 844, "world", "system", False),
    ("narrow-phone-multiplayer", 360, 800, "multiplayer", "system", False),
    ("landscape-ambience", 844, 390, "ambience", "system", False),
    ("short-desktop-dialogue", 1280, 600, "dialogue", "system", False),
    ("zoom-equivalent-attire", 640, 360, "attire", "system", False),
    ("japanese-attire", 390, 844, "attire", "system", True),
    ("reduced-backdrop", 1280, 820, "backdrops", "reduce", False),
    ("effects-off-backdrop", 390, 844, "backdrops", "off", False),
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
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def fulfill(route: Route, payload: object, status: int = 200) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload, ensure_ascii=False, sort_keys=True))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash() -> str:
    digest = hashlib.sha256()
    roots = (ROOT / "static" / "css" / "ui", ROOT / "static" / "js" / "ui-next")
    files = [path for base in roots for path in base.rglob("*") if path.is_file()]
    files += [ROOT / "static" / "ui-next.html", ROOT / "language_packs" / "en" / "ui.json", ROOT / "language_packs" / "ja" / "ui.json"]
    for path in sorted(files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode()); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


def boot(japanese: bool) -> dict:
    messages = json.loads((ROOT / "language_packs" / "ja" / "ui.json").read_text(encoding="utf-8")) if japanese else {}
    return {
        "ui_language": "ja" if japanese else "en", "ui_direction": "ltr", "ui_messages": messages,
        "chats": [{"id": 1, "name": "The Lantern Archive"}],
        "characters": [{"id": 7, "name": "Mara"}, {"id": 8, "name": "Ivo"}],
        "personas": [{"id": 3, "name": "Rin"}], "lorebooks": [], "providers": [],
        "language_packs": [{"id": "en", "name": "English", "native_name": "English", "story": True, "ui": True}],
        "extensions": [], "extension_errors": [], "extension_lanes": [],
    }


def story() -> dict:
    return {
        "chat": {"id": 1, "name": "The Lantern Archive", "story_language": "en"},
        "frames": [{"id": None, "label": "Present"}, {"id": 5, "label": "Courtyard"}],
        "turns": [{"id": 11, "idx": 0, "frame_id": None, "player_input": "Listen", "prose": "Rain combs the archive windows while the old lamps burn.", "speech": [], "stale": False, "stale_from": None, "prose_stale": False}],
        "participants": [{"id": 7, "name": "Mara", "status": "active"}],
        "dialogue_colors": {"Mara": "#6ebf99"},
    }


WORLD = {"scene": {"location": "Archive", "rooms": {"archive": {"name": "Archive"}, "court": {"name": "Courtyard"}}, "entities": {"lamp": {"name": "Lamp"}}, "positions": {"Mara": "archive"}, "world_conditions": [{"kind": "rain"}]}, "pending": [{"type": "arrival", "who": "Ivo"}]}
ATTIRE = {"Mara": {"wearing": ["linen coat"], "state": ["rain-darkened"], "regions": {"torso": ["linen coat"]}}}
DIALOGUE = {"style": "natural", "min_lines": 0, "max_lines": 4, "variance": .6, "autonomy": 50, "allow_npc_initiative": True, "allow_npc_to_npc_dialogue": True, "stop_on_player_address": True, "stop_on_question_to_player": True, "silence_ends_exchange": True, "initial_parallel_reactors": 1, "parallel_isolated_reactors": False, "promote_after_addressed": 0, "offscreen_life": "stochastic", "max_offscreen_actors": 3, "offscreen_life_levels": [{"value": "stochastic", "description": "logs", "built": True}]}
BACKDROP = {"enabled": True, "configured": True, "room": "Archive", "room_id": "archive", "signature": "backdrop-a", "ready": True, "status": "ready", "error": None, "url": "/static/assets/theme-textures/stone-slate.png", "weather": {"precipitation": "rain", "intensity": "heavy", "severity": "seasonal"}}
AMBIENCE = {"enabled": True, "configured": True, "source": "library", "room": "Archive", "room_id": "archive", "signature": "amb-a", "pinned": False, "gain": .8, "ready": True, "silent": False, "reason": "", "status": "ready", "error": None, "error_kind": None, "url": "/media/amb-a.audio", "token": "amb-a#1", "layers": [{"index": 0, "role": "tone", "gain": 1, "title": "Archive rain", "source": "library", "path": "rain.ogg", "license": "CC0", "username": "Field recordist", "credit_url": "", "query": "rain archive", "url": "/media/amb-a.audio"}], "track": {"title": "Archive rain", "source": "library"}}


def route_case(page: Page, japanese: bool) -> list[str]:
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))

    def handler(route: Route) -> None:
        request = route.request
        path = urlparse(request.url).path
        method = request.method
        if path == "/api/bootstrap": payload = boot(japanese)
        elif path == "/api/chats/1": payload = story()
        elif path == "/api/chats/1/positions": payload = {"rooms": [{"id": "archive", "name": "Archive"}, {"id": "court", "name": "Courtyard"}], "characters": [{"id": 7, "name": "Mara", "room": "archive"}], "persona": {"name": "Rin", "room": "archive"}}
        elif path == "/api/chats/1/vitals": payload = {"enabled": True, "show_npcs": True, "player": {"name": "Rin", "is_player": True, "vitals": {"breath": 76, "stamina": 64, "nourishment": 48}}, "characters": [{"name": "Mara", "is_player": False, "vitals": {"breath": 90, "stamina": 82}}]}
        elif path == "/api/chats/1/world": payload = WORLD
        elif path == "/api/chats/1/attire": payload = ATTIRE
        elif path == "/api/chats/1/style_guide": payload = {"style_guide": {"genre": "gothic", "tone": "quiet", "weather_severity": "seasonal", "director_notes": "", "mapping_notes": "", "avoid": ""}, "fields": ["genre", "tone", "weather_severity", "director_notes", "mapping_notes", "avoid"]}
        elif path == "/api/chats/1/language": payload = {"language": "en", "stored": "en", "installed": True}
        elif path == "/api/chats/1/survival": payload = {"enabled": True, "show_npcs": True}
        elif path == "/api/chats/1/player_authority": payload = {"mode": "world_author", "modes": [{"value": "world_author", "grants": []}, {"value": "actor_only", "grants": []}]}
        elif path == "/api/chats/1/dialogue_config": payload = DIALOGUE
        elif path == "/api/chats/1/background_config": payload = {"scene_life": "off", "max_managed": 6, "max_reactors": 1}
        elif path == "/api/chats/1/living_world": payload = {"living_world": {"routine_residue": "off"}, "approaches": [{"approach": "routine_residue", "label": "Routine residue", "value": "off", "depths": []}]}
        elif path == "/api/chats/1/frames": payload = {"frames": story()["frames"]}
        elif path == "/api/chats/1/personas": payload = {"personas": [{"id": 3, "name": "Rin", "station": "archive"}]}
        elif path == "/api/chats/1/guest_invites": payload = {"invites": [{"id": 9, "label": "Table guest", "expires_at": "tomorrow"}]}
        elif path == "/api/turns/11/backdrop": payload = BACKDROP
        elif path == "/api/turns/11/ambience": payload = AMBIENCE
        elif path == "/api/chats/1/ambience/pins": payload = {"pins": {}}
        elif method in {"POST", "PUT", "DELETE"}: payload = {"ok": True}
        else:
            fulfill(route, {"detail": path}, 404); return
        fulfill(route, payload)

    page.route("**/api/**", handler)
    return requests


def inspect(page: Page, requests: list[str]) -> dict:
    metrics = page.evaluate("""() => {
      const visible = node => { const r = node.getBoundingClientRect(); return r.width > 1 && r.height > 1 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
      const controls = [...document.querySelectorAll('button,input,select,textarea,a[href]')].filter(visible);
      const effective = node => node.matches('input') && node.closest('label') ? node.closest('label').getBoundingClientRect() : node.getBoundingClientRect();
      const rects = controls.map(node => { const r = effective(node); return {label: node.getAttribute('aria-label') || node.textContent.trim(), width: r.width, height: r.height}; });
      const transcript = document.querySelector('[data-play-transcript]')?.getBoundingClientRect();
      const composer = document.querySelector('[data-play-composer]')?.getBoundingClientRect();
      const panelNode = [...document.querySelectorAll('[data-story-tool-panel]')].find(visible);
      const panel = panelNode?.getBoundingClientRect();
      const overlap = (a, b) => a && b && Math.max(0, Math.min(a.right,b.right)-Math.max(a.left,b.left)) * Math.max(0, Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
      return {
        layout_state: document.documentElement.dataset.layoutState,
        horizontal_overflow_px: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        undersized_compact_targets: document.documentElement.dataset.layoutState === 'compact' ? rects.filter(row => Math.min(row.width,row.height) < 44) : [],
        tool_id: new URLSearchParams(location.hash.split('?')[1] || '').get('tool'),
        tool_visible: Boolean(panelNode),
        transcript_composer_overlap_px2: overlap(transcript, composer),
        panel_composer_overlap_px2: overlap(panel, composer),
        classic_global: Object.hasOwn(window, 'S'),
        sensitive_text: /password|api[_ -]?key|join code|cookie|session=/i.test(document.body.textContent),
        dom_count: document.querySelectorAll('*').length,
        weather_visible: Boolean(document.querySelector('[data-play-weather]') && visible(document.querySelector('[data-play-weather]'))),
        backdrop_visible: Boolean(document.querySelector('[data-play-backdrop]') && visible(document.querySelector('[data-play-backdrop]'))),
      };
    }""")
    metrics["api_requests"] = sorted(urlparse(url).path for url in requests if "/api/" in urlparse(url).path)
    return metrics


def capture() -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True); SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    results = []
    with serve_root() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        browser_version = browser.version
        for case_id, width, height, tool, motion, japanese in CASES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.emulate_media(reduced_motion="reduce" if motion == "reduce" else "no-preference")
            if motion == "off":
                page.add_init_script("localStorage.setItem('sonder.ui-next', JSON.stringify({version:2,appearance:{motion:'off'},navigation:{},panes:{},drafts:{}}))")
            errors: list[str] = []; console_errors: list[str] = []
            page.on("pageerror", lambda error, rows=errors: rows.append(str(error)))
            page.on("console", lambda message, rows=console_errors: rows.append(message.text) if message.type == "error" else None)
            requests = route_case(page, japanese)
            response = page.goto(f"{base_url}/static/ui-next.html#/play/story-tools?chat=1&tool={tool}")
            if response is None or not response.ok: raise RuntimeError(case_id)
            page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
            page.wait_for_function("[...document.querySelectorAll('[data-story-tool-panel]')].some(node => { const r = node.getBoundingClientRect(); return r.width > 1 && r.height > 1; })")
            page.wait_for_function("document.fonts.status === 'loaded'")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            screenshot = SCREENSHOTS / f"{case_id}.png"
            page.screenshot(path=screenshot, animations="disabled")
            results.append({"id": case_id, "viewport": {"width": width, "height": height}, "motion": motion, "language": "ja" if japanese else "en", **inspect(page, requests), "page_errors": errors, "console_errors": console_errors, "screenshot": screenshot.relative_to(ROOT).as_posix(), "screenshot_sha256": sha256(screenshot)})
            page.close()
        browser.close()
    return {"schema_version": 1, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_tree_sha256": tree_hash(), "browser": f"Chromium {browser_version}", "platform": platform.platform(), "cases": results}


def main() -> None:
    report = capture()
    output = OUTPUT / "story-tools-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(report['cases'])} cases to {output}")


if __name__ == "__main__":
    main()
