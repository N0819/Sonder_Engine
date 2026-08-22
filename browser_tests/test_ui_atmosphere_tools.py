"""Browser journeys for replacement backdrops, weather, ambience, and chime."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect


BOOT = {
    "ui_language": "en", "ui_direction": "ltr", "ui_messages": {},
    "chats": [{"id": 1, "name": "Lantern Archive"}],
    "characters": [], "personas": [], "lorebooks": [], "providers": [],
    "language_packs": [], "extensions": [], "extension_errors": [],
    "extension_lanes": [],
}


def _story():
    return {
        "chat": {"id": 1, "name": "Lantern Archive"},
        "frames": [{"id": None, "label": "Present"}],
        "turns": [{
            "id": 11, "idx": 0, "frame_id": None, "player_input": "Listen",
            "prose": "Rain combs the archive windows while the old lamps burn.",
            "speech": [], "stale": False, "stale_from": None,
            "prose_stale": False,
        }],
        "participants": [], "dialogue_colors": {},
    }


def _open(page: Page, ui_base_url: str, *, tool: str, backdrop=None, ambience=None):
    state = {
        "calls": [],
        "backdrop_on_post": None,
        "backdrop": backdrop or {
            "enabled": True, "configured": True, "room": "Archive",
            "room_id": "archive", "signature": "backdrop-a", "ready": True,
            "status": "ready", "error": None,
            "url": "/media/backdrop-a.png",
            "weather": {"kind": "rain", "severity": "seasonal"},
        },
        "ambience": ambience or {
            "enabled": True, "configured": True, "source": "library",
            "room": "Archive", "room_id": "archive", "signature": "amb-a",
            "pinned": False, "gain": 0.8, "ready": True, "silent": False,
            "reason": "", "status": "ready", "error": None,
            "error_kind": None, "url": "/media/amb-a.audio", "token": "amb-a#1",
            "layers": [{"index": 0, "role": "tone", "gain": 1,
                        "title": "Archive rain", "source": "library",
                        "path": "rain.ogg", "license": "", "username": "",
                        "credit_url": "", "query": "rain archive",
                        "url": "/media/amb-a.audio"}],
            "track": {"title": "Archive rain", "source": "library"},
        },
    }

    page.add_init_script("""
      window.__audioEvents = [];
      class TestAudio extends EventTarget {
        constructor(url = '') { super(); this.src = url; this.volume = 1; this.loop = false; this.paused = true; }
        play() { this.paused = false; window.__audioEvents.push(['play', this.src, this.volume]); return Promise.resolve(); }
        pause() { this.paused = true; window.__audioEvents.push(['pause', this.src]); }
        load() {}
      }
      window.Audio = TestAudio;
    """)

    def route_api(route):
        request = route.request
        path = urlparse(request.url).path
        state["calls"].append((request.method, path))
        if path == "/api/bootstrap": payload = BOOT
        elif path == "/api/chats/1": payload = _story()
        elif path == "/api/turns/11/backdrop":
            if request.method == "POST" and state["backdrop_on_post"]:
                state["backdrop"] = state["backdrop_on_post"]
            payload = state["backdrop"]
        elif path == "/api/turns/11/ambience": payload = state["ambience"]
        elif path == "/api/chats/1/ambience/pins": payload = {"pins": {}}
        elif path == "/api/chats/1/ambience/pin": payload = {"ok": True, "room": "archive", "pin": {}}
        elif path == "/api/chats/1/ambience/oneshot/thunder": payload = {
            "name": "thunder", "variant": 0, "status": "ready", "ready": True,
            "error": None, "url": "/media/thunder.audio",
        }
        else:
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"detail": path}))
            return
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    page.route("**/api/**", route_api)
    response = page.goto(
        f"{ui_base_url}/static/ui-next.html#/play/story-tools?chat=1&tool={tool}"
    )
    assert response and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    return state


def test_ready_backdrop_and_weather_do_not_change_reading_or_composer_geometry(
    page: Page, ui_base_url: str
):
    ready = {
        "enabled": True, "configured": True, "room": "Archive",
        "room_id": "archive", "signature": "backdrop-a", "ready": True,
        "status": "ready", "error": None, "url": "/media/backdrop-a.png",
        "weather": {"kind": "rain", "severity": "seasonal"},
    }
    state = _open(page, ui_base_url, tool="backdrops", backdrop={
        **ready, "signature": "backdrop-empty", "ready": False,
        "status": "absent", "url": None, "weather": {},
    })
    state["backdrop_on_post"] = ready
    transcript = page.locator("[data-play-transcript]")
    composer = page.locator("[data-play-composer]")
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role(
        "button", name="Generate backdrop"
    ).click()
    expect(page.locator("[data-play-backdrop]")).to_have_attribute("src", "/media/backdrop-a.png")
    expect(page.locator("[data-play-weather]")).to_have_attribute("data-weather", "rain")
    expect(page.get_by_role("complementary", name="Story tools").get_by_text("Backdrop ready")).to_be_visible()
    page.wait_for_timeout(150)
    before = page.evaluate("""() => ({
      transcript: document.querySelector('[data-play-transcript]').getBoundingClientRect().toJSON(),
      composer: document.querySelector('[data-play-composer]').getBoundingClientRect().toJSON()
    })""")
    state["backdrop_on_post"] = {
        **ready, "signature": "backdrop-b", "url": "/media/backdrop-b.png",
    }
    panel.get_by_role("button", name="Generate a different backdrop").click()
    expect(page.locator("[data-play-backdrop]")).to_have_attribute("src", "/media/backdrop-b.png")
    page.wait_for_timeout(150)
    after = page.evaluate("""() => ({
      transcript: document.querySelector('[data-play-transcript]').getBoundingClientRect().toJSON(),
      composer: document.querySelector('[data-play-composer]').getBoundingClientRect().toJSON()
    })""")
    assert before == after
    assert transcript.is_visible() and composer.is_visible()
    assert state["calls"].count(("GET", "/api/turns/11/backdrop")) == 1


def test_pending_backdrop_waits_for_an_explicit_status_check_without_polling(
    page: Page, ui_base_url: str
):
    state = _open(page, ui_base_url, tool="backdrops", backdrop={
        "enabled": True, "configured": True, "room": "Archive",
        "room_id": "archive", "signature": "backdrop-p", "ready": False,
        "status": "pending", "error": None, "url": None, "weather": {},
    })
    panel = page.get_by_role("complementary", name="Story tools")
    expect(panel.get_by_text("Backdrop is being prepared.")).to_be_visible()
    page.wait_for_timeout(900)
    assert state["calls"].count(("GET", "/api/turns/11/backdrop")) == 1
    panel.get_by_role("button", name="Check status").click()
    page.wait_for_timeout(150)
    assert state["calls"].count(("GET", "/api/turns/11/backdrop")) == 2


def test_ambience_controls_persist_outside_tool_dom_and_pause_while_hidden(
    page: Page, ui_base_url: str
):
    _open(page, ui_base_url, tool="ambience")
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role("button", name="Enable audio").click()
    page.wait_for_function("window.__audioEvents.some(e => e[0] === 'play')")
    panel.get_by_label("Ambience volume").fill("0.35")
    panel.get_by_role("checkbox", name="Completion chime").check()
    panel.get_by_role("button", name="Mute").click()
    assert page.evaluate("window.__audioEvents.some(e => e[0] === 'pause')")
    saved = page.evaluate("JSON.parse(localStorage.getItem('sonder.ui-next')).panes.atmosphere")
    assert saved == {"muted": True, "volume": 0.35, "chime": True}
    page.get_by_role("button", name="World", exact=True).click()
    assert page.evaluate("window.__audioEvents.length") > 0


def test_effects_off_keeps_static_backdrop_and_removes_weather_overlay(
    page: Page, ui_base_url: str
):
    page.add_init_script("""
      localStorage.setItem('sonder.ui-next', JSON.stringify({
        version: 2, appearance: {motion: 'off'}, navigation: {}, panes: {}, drafts: {}
      }));
    """)
    _open(page, ui_base_url, tool="backdrops")
    expect(page.locator("[data-play-backdrop]")).to_be_visible()
    weather = page.locator("[data-play-weather]")
    expect(weather).to_be_hidden()
    cluster = page.locator(".ui-play__audio-cluster")
    sizes = cluster.locator("button,input").evaluate_all(
        "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); return [r.width, r.height]; })"
    )
    assert all(min(width, height) >= 44 for width, height in sizes)
