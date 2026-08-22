"""Real-browser journeys for Cast, Conditions, Frames, and Multiplayer."""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect


BOOT = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [{"id": 1, "name": "The Lantern Archive"}],
    "characters": [
        {"id": 7, "name": "Mara"},
        {"id": 8, "name": "Ivo"},
    ],
    "personas": [
        {"id": 20, "name": "Rin"},
        {"id": 21, "name": "Sol"},
    ],
    "lorebooks": [],
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _host(page: Page, ui_base_url: str, *, width: int = 1280):
    state = {
        "participants": [
            {"id": 7, "name": "Mara", "status": "active", "dialogue_color": ""}
        ],
        "frames": [
            {"id": None, "label": "Present", "kind": "present", "travelers": [], "nonexistent_cast": []},
            {"id": 31, "label": "Far future", "kind": "future", "travelers": [7], "nonexistent_cast": []},
        ],
        "personas": [{"id": 20, "name": "Rin", "frame_id": None}],
        "grants": [],
        "requests": [],
        "errors": [],
    }
    page.on("pageerror", lambda error: state["errors"].append(str(error)))

    def route_api(route):
        request = route.request
        path = request.url.split(ui_base_url, 1)[-1]
        method = request.method
        state["requests"].append((method, path))
        body = request.post_data_json if request.post_data else {}
        if path == "/api/bootstrap":
            payload = BOOT
        elif path == "/api/chats/1":
            payload = {
                "chat": {"id": 1, "name": "The Lantern Archive"},
                "frames": state["frames"],
                "turns": [],
                "participants": state["participants"],
                "dialogue_colors": {"Mara": "#6688cc"},
            }
        elif path.startswith("/api/chats/1/positions"):
            payload = {
                "rooms": [{"id": "archive", "name": "Archive", "parent_name": None}],
                "characters": [{"id": 7, "name": "Mara", "status": "active", "room": "archive"}],
                "persona": {"name": "Rin", "room": "archive"},
            }
        elif path.startswith("/api/chats/1/vitals"):
            payload = {
                "enabled": True,
                "show_npcs": True,
                "bodies": [
                    {"name": "Rin", "is_player": True,
                     "vitals": {"air": .9, "stamina": .6, "nourishment": .7, "injury": .1},
                     "labels": {"air": "clear", "stamina": "steady", "nourishment": "fed", "injury": "minor"}},
                    {"name": "Mara", "is_player": False,
                     "vitals": {"air": .7, "stamina": .4, "nourishment": .5, "injury": .3},
                     "labels": {"air": "clear", "stamina": "tired", "nourishment": "hungry", "injury": "hurt"}},
                ],
            }
        elif path == "/api/chats/1/frames":
            if method == "POST":
                state["frames"].append({"id": 32, **body, "travelers": body.get("travelers", []), "nonexistent_cast": body.get("nonexistent_cast", [])})
                payload = state["frames"][-1]
            else:
                payload = {"frames": state["frames"]}
        elif path == "/api/chats/1/personas":
            if method == "POST":
                state["personas"].append({"id": body["persona_id"], "name": "Sol", "frame_id": None})
                payload = {"ok": True}
            else:
                payload = {"personas": state["personas"]}
        elif path == "/api/chats/1/guest_invites":
            if method == "POST":
                state["grants"] = [{"id": 91, "persona_id": body["persona_id"], "status": "pending"}]
                payload = {"grant_id": 91, "code": "one-time-secret", "expires": 9999999999}
            else:
                payload = {"grants": state["grants"]}
        elif path == "/api/chats/1/characters/7" and method == "DELETE":
            state["participants"][0]["status"] = "dormant"
            payload = {"ok": True}
        elif path.startswith("/api/chats/1/characters/7/position"):
            payload = {"ok": True, "name": "Mara", "room": body.get("room")}
        elif path == "/api/chats/1/characters/7/dialogue_color":
            payload = {"ok": True, "color": body.get("color", ""), "dialogue_colors": {"Mara": body.get("color") or "#6688cc"}}
        elif path == "/api/chats/1/personas/20/station":
            state["personas"][0]["frame_id"] = body.get("frame_id")
            payload = {"ok": True, "frame_id": body.get("frame_id")}
        elif path == "/api/chats/1/guest_invites/91" and method == "DELETE":
            state["grants"] = []
            payload = {"ok": True}
        elif path == "/api/chats/1/personas/20" and method == "DELETE":
            state["personas"] = []
            payload = {"ok": True}
        else:
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"detail": path}))
            return
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    page.set_viewport_size({"width": width, "height": 820})
    page.route("**/api/**", route_api)
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play/story-tools?chat=1&tool=cast")
    assert response and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    return state


def test_cast_and_conditions_render_authoritative_state_without_covering_play(page: Page, ui_base_url: str):
    state = _host(page, ui_base_url)
    page.wait_for_timeout(500)
    assert state["errors"] == [], state["errors"]
    assert ("GET", "/api/chats/1/positions") in state["requests"], state["requests"]
    panel = page.get_by_role("complementary", name="Story tools")
    expect(panel.get_by_role("heading", name="Mara")).to_be_visible()
    expect(panel.get_by_role("combobox", name="Current location: Mara")).to_have_value("archive")
    panel.get_by_role("button", name="Move to dormant").click()
    expect(panel.get_by_role("button", name="Restore to active")).to_be_visible()
    assert ("DELETE", "/api/chats/1/characters/7") in state["requests"]

    panel.get_by_role("button", name="Conditions", exact=True).click()
    expect(panel.get_by_role("heading", name="Rin")).to_be_visible()
    expect(panel.get_by_role("progressbar")).to_have_count(8)
    transcript = page.locator("[data-play-transcript]").bounding_box()
    composer = page.locator("[data-play-composer]").bounding_box()
    conditions = panel.locator(".ui-conditions").bounding_box()
    assert transcript and composer and conditions
    assert conditions["x"] >= transcript["x"] + transcript["width"]
    assert composer["y"] >= transcript["y"]


def test_frames_switch_create_and_station_without_losing_tool_route(page: Page, ui_base_url: str):
    state = _host(page, ui_base_url)
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role("button", name="Frames", exact=True).click()
    expect(panel.get_by_role("heading", name="Far future")).to_be_visible()
    panel.get_by_role("button", name="Open frame: Far future").click()
    expect(page).to_have_url(re.compile(r"tool=frames.*frame=31|frame=31.*tool=frames"))

    panel.get_by_label("Frame name").fill("Deep past")
    panel.get_by_role("button", name="Create frame").click()
    expect(panel.get_by_role("heading", name="Deep past")).to_be_visible()
    panel.get_by_role("combobox", name="Rin: Participant stationing").select_option("31")
    page.wait_for_timeout(100)
    assert ("PUT", "/api/chats/1/personas/20/station") in state["requests"]


def test_invite_secret_is_ephemeral_and_revocation_is_in_context(page: Page, ui_base_url: str):
    state = _host(page, ui_base_url)
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role("button", name="Multiplayer", exact=True).click()
    panel.get_by_role("button", name="Create invite").click()
    secret = panel.locator("[data-invite-secret]")
    expect(secret).to_contain_text("one-time-secret")
    storage = page.evaluate("Object.values(localStorage).join(' ')")
    assert "one-time-secret" not in storage
    panel.get_by_role("button", name="Revoke invite").click()
    expect(panel.get_by_role("button", name="Create invite")).to_be_visible()
    assert ("DELETE", "/api/chats/1/guest_invites/91") in state["requests"]
