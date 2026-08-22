"""Browser journeys for World, Style, Dialogue, and Attire author controls."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


BOOT = {
    "ui_language": "en", "ui_direction": "ltr", "ui_messages": {},
    "chats": [{"id": 1, "name": "The Lantern Archive"}],
    "characters": [], "personas": [], "lorebooks": [], "providers": [],
    "language_packs": [
        {"id": "en", "name": "English", "native_name": "English", "story": True, "ui": True},
        {"id": "ja", "name": "Japanese", "native_name": "日本語", "story": True, "ui": True},
    ],
    "extensions": [], "extension_errors": [], "extension_lanes": [],
}


def _open(page: Page, ui_base_url: str, *, width: int = 1280, japanese: bool = False):
    world = {
        "scene": {
            "location": "Archive",
            "rooms": {"archive": {"name": "Archive"}},
            "entities": {"lamp": {"name": "Lamp"}},
            "positions": {"Rin": "archive"},
            "world_conditions": [{"kind": "rain"}],
        },
        "pending": [{"type": "arrival", "who": "Mara"}],
    }
    attire = {
        "Rin": {
            "wearing": ["linen coat"],
            "state": ["rain-darkened"],
            "regions": {"torso": ["linen coat"]},
        },
        "Wearing": {"wearing": [], "state": [], "regions": {}},
    }
    dialogue = {
        "style": "natural", "min_lines": 0, "max_lines": 4, "variance": .6,
        "autonomy": 50, "allow_npc_initiative": True,
        "allow_npc_to_npc_dialogue": True, "stop_on_player_address": True,
        "stop_on_question_to_player": True, "silence_ends_exchange": True,
        "initial_parallel_reactors": 1, "parallel_isolated_reactors": False,
        "promote_after_addressed": 0, "offscreen_life": "stochastic",
        "max_offscreen_actors": 3,
        "offscreen_life_levels": [
            {"value": "inert", "description": "none", "built": True},
            {"value": "stochastic", "description": "logs", "built": True},
        ],
    }
    state = {"puts": [], "world": world, "attire": attire, "dialogue": dialogue}

    def route_api(route):
        request = route.request
        path = request.url.split(ui_base_url, 1)[-1]
        method = request.method
        body = request.post_data_json if request.post_data else None
        if method == "PUT":
            state["puts"].append((path, body))
        payload = None
        if path == "/api/bootstrap":
            payload = {
                **BOOT,
                **({
                    "ui_language": "ja",
                    "ui_messages": {
                        "Attire": "服装",
                        "Wearing": "着用中",
                        "Body regions": "身体部位",
                        "Visible state": "見えている状態",
                    },
                } if japanese else {}),
            }
        elif path == "/api/chats/1":
            payload = {
                "chat": {"id": 1, "name": "The Lantern Archive", "story_language": "en"},
                "frames": [{"id": None, "label": "Present"}], "turns": [],
                "participants": [], "dialogue_colors": {},
            }
        elif path == "/api/chats/1/positions":
            payload = {"rooms": [], "characters": [], "persona": {"name": "Rin", "room": None}}
        elif path == "/api/chats/1/world":
            if method == "PUT":
                state["world"] = body
                payload = {"ok": True}
            else:
                payload = state["world"]
        elif path == "/api/chats/1/attire":
            if method == "PUT":
                state["attire"] = body
                payload = {"ok": True}
            else:
                payload = state["attire"]
        elif path == "/api/chats/1/style_guide":
            payload = {"style_guide": body.get("style_guide", {})} if method == "PUT" else {
                "style_guide": {"genre": "gothic", "tone": "quiet", "weather_severity": "seasonal",
                                "director_notes": "", "mapping_notes": "", "avoid": ""},
                "fields": ["genre", "tone", "weather_severity", "director_notes", "mapping_notes", "avoid"],
            }
        elif path == "/api/chats/1/language":
            payload = {"language": body["language"], "stored": body["language"], "installed": True} if method == "PUT" else {
                "language": "en", "stored": "en", "installed": True,
            }
        elif path == "/api/chats/1/survival":
            payload = body if method == "PUT" else {"enabled": False, "show_npcs": False}
        elif path == "/api/chats/1/player_authority":
            payload = {"mode": body["mode"]} if method == "PUT" else {
                "mode": "world_author",
                "modes": [{"value": "world_author", "grants": []}, {"value": "actor_only", "grants": []}],
            }
        elif path == "/api/chats/1/dialogue_config":
            if method == "PUT":
                state["dialogue"] = body
                payload = body
            else:
                payload = state["dialogue"]
        elif path == "/api/chats/1/background_config":
            payload = body if method == "PUT" else {"scene_life": "off", "max_managed": 6, "max_reactors": 1}
        elif path == "/api/chats/1/living_world":
            payload = {"ok": True, "living_world": body.get("living_world", {})} if method == "PUT" else {
                "living_world": {"routine_residue": "off"},
                "approaches": [{"approach": "routine_residue", "label": "Routine residue", "value": "off", "depths": []}],
            }
        else:
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"detail": path}))
            return
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    page.set_viewport_size({"width": width, "height": 820})
    page.route("**/api/**", route_api)
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play/story-tools?chat=1&tool=world")
    assert response and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    return state


def test_world_complete_draft_survives_navigation_and_saves_verbatim(page: Page, ui_base_url: str):
    state = _open(page, ui_base_url)
    panel = page.get_by_role("complementary", name="Story tools")
    expect(panel.get_by_text("Rooms")).to_be_visible()
    panel.get_by_text("Advanced JSON", exact=True).click()
    editor = panel.get_by_role("textbox", name="world JSON")
    draft = {**state["world"], "manual_note": {"reason": "keep complete payload"}}
    editor.fill(json.dumps(draft, indent=2))
    panel.get_by_role("button", name="Attire", exact=True).click()
    expect(panel.get_by_role("heading", name="Rin", exact=True)).to_be_visible()
    panel.get_by_role("button", name="World", exact=True).click()
    panel.get_by_text("Advanced JSON", exact=True).click()
    expect(panel.get_by_role("textbox", name="world JSON")).to_have_value(json.dumps(draft, indent=2))
    panel.get_by_role("button", name="Save changes").click()
    expect(panel.get_by_role("status").filter(has_text="Changes saved.")).to_be_visible()
    assert ("/api/chats/1/world", draft) in state["puts"]


def test_style_save_changes_story_owned_fields_but_never_host_ui_language(page: Page, ui_base_url: str):
    state = _open(page, ui_base_url)
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role("button", name="Style", exact=True).click()
    panel.get_by_label("Genre").fill("weird western")
    panel.get_by_label("Story language").select_option("ja")
    panel.get_by_label("Player authority").select_option("actor_only")
    panel.get_by_label("Track bodily condition").check()
    panel.get_by_role("button", name="Save changes").click()
    expect(panel.get_by_role("status").filter(has_text="Changes saved.")).to_be_visible()
    paths = [path for path, _body in state["puts"]]
    assert "/api/chats/1/style_guide" in paths
    assert "/api/chats/1/language" in paths
    assert "/api/chats/1/survival" in paths
    assert "/api/chats/1/player_authority" in paths
    assert "/api/ui-language" not in paths
    assert next(body for path, body in state["puts"] if path == "/api/chats/1/language") == {"language": "ja"}


def test_dialogue_validation_blocks_partial_write_then_saves_all_documents(page: Page, ui_base_url: str):
    state = _open(page, ui_base_url)
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role("button", name="Dialogue", exact=True).click()
    panel.get_by_label("Maximum lines").fill("-1")
    panel.get_by_role("button", name="Save changes").click()
    expect(panel.get_by_role("status").filter(has_text="max_lines must be 0 or more.")).to_be_visible()
    assert not any(path.endswith("dialogue_config") for path, _body in state["puts"])
    panel.get_by_label("Maximum lines").fill("6")
    panel.get_by_role("button", name="Save changes").click()
    expect(panel.get_by_role("status").filter(has_text="Changes saved.")).to_be_visible()
    paths = [path for path, _body in state["puts"]]
    assert paths[-3:] == [
        "/api/chats/1/dialogue_config",
        "/api/chats/1/background_config",
        "/api/chats/1/living_world",
    ]


def test_attire_summary_and_advanced_save_preserve_region_structure(page: Page, ui_base_url: str):
    state = _open(page, ui_base_url)
    panel = page.get_by_role("complementary", name="Story tools")
    panel.get_by_role("button", name="Attire", exact=True).click()
    expect(panel.get_by_role("heading", name="Rin", exact=True)).to_be_visible()
    expect(panel.get_by_text("Body regions: torso")).to_be_visible()
    panel.get_by_text("Advanced JSON", exact=True).click()
    payload = {**state["attire"], "Mara": {"wearing": [], "state": [], "regions": {}}}
    panel.get_by_role("textbox", name="attire JSON").fill(json.dumps(payload))
    panel.get_by_role("button", name="Save changes").click()
    expect(panel.get_by_role("status").filter(has_text="Changes saved.")).to_be_visible()
    assert ("/api/chats/1/attire", payload) in state["puts"]


def test_mobile_japanese_chrome_keeps_story_data_literal_and_has_no_page_overflow(page: Page, ui_base_url: str):
    _open(page, ui_base_url, width=390, japanese=True)
    page.get_by_role("button", name="Open context panel").click()
    sheet = page.get_by_role("dialog", name="Story tools")
    sheet.get_by_role("button", name="服装", exact=True).click()
    expect(sheet.get_by_role("heading", name="Wearing", exact=True)).to_be_visible()
    expect(sheet.get_by_text("着用中", exact=True).first).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
