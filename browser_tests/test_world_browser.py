"""The World Browser in a real browser: the tree, the card, walking an exit,
and the Raw JSON tab that keeps the old editors.

Fully mocked at the network boundary. What `node --check` cannot see is the
part worth testing here: that the 🌍 button opens on Browse, that clicking an
exit re-selects the far room in the tree and re-renders the card, that the
Raw JSON tab still offers the world table for hand repair, and that 👕 opens
the same dialog with the attire rows unfolded.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP, _chat_payload


def _row(rid, name, hops, occupants=(), status="live", holder=None,
         holder_name=None, holder_room=None):
    return {"id": rid, "name": name, "status": status, "holder": holder,
            "hops": hops, "holder_name": holder_name, "holder_room": holder_room,
            "occupants": list(occupants)}


INDEX = {
    "frame_id": None,
    "location": "Old Manor",
    "groups": {
        "cast": [_row("kitchen", "Kitchen", 0, ["Alice"]),
                 _row("study", "Study", 0, ["Nathan"])],
        "reachable": [_row("hallway", "Hallway", 1),
                      _row("console_room", "Console Room", 1, holder="tardis",
                           holder_name="The TARDIS", holder_room="study"),
                      _row("attic", "Attic", 2, status="planned")],
        "unreachable": [_row("crypt", "Crypt", None, status="planned")],
        "retired": [_row("old_wing", "Old Wing", None, status="retired")],
    },
}


def _slice(rid, name, desc, exits, occupants=()):
    return {"id": rid, "name": name, "status": "live", "holder": None,
            "holder_name": None, "description": desc, "exits": exits,
            "occupants": list(occupants), "things": [], "planned_stub": None,
            "plan_here": {"planned_entities": [], "needs": [], "package_ops": []}}


SLICES = {
    "kitchen": _slice("kitchen", "Kitchen", "A rustic kitchen with a heavy oak table.",
                      [{"to": "hallway", "name": "Hallway", "barrier": "open",
                        "dir": None, "status": "live"},
                       {"to": "attic", "name": "Attic", "barrier": None,
                        "dir": "up", "status": "planned"}],
                      [{"name": "Alice", "station": None,
                        "attire": {"wearing": ["apron"], "state": [],
                                   "regions": {"torso": {"garments": [
                                       {"name": "apron", "state": "worn"}],
                                       "beneath": ""}}}}]),
    "hallway": _slice("hallway", "Hallway", "A long, dim hallway.",
                      [{"to": "kitchen", "name": "Kitchen", "barrier": "open",
                        "dir": None, "status": "live"}]),
}

POSITIONS = {
    "rooms": [], "location": "Old Manor",
    "characters": [{"id": 9, "name": "Alice", "status": "active", "room": "kitchen"},
                   {"id": 10, "name": "Bob", "status": "active", "room": "hallway"}],
    "persona": {"name": "Nathan", "room": "kitchen"},
}


def _mount(page: Page) -> list[str]:
    bootstrap = {**BOOTSTRAP, "chats": [{"id": 1, "name": "First"}]}
    seen: list[str] = []

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        seen.append(path)
        if path == "/api/bootstrap":
            body = bootstrap
        elif path == "/api/chats/1":
            body = _chat_payload(1, "First", "settled prose")
        elif path == "/api/chats/1/vitals":
            body = {"enabled": False, "bodies": []}
        elif path == "/api/chats/1/rooms":
            body = INDEX
        elif path.startswith("/api/chats/1/rooms/"):
            body = SLICES[path.rsplit("/", 1)[1]]
        elif path == "/api/chats/1/positions":
            body = POSITIONS
        elif path == "/api/chats/1/world":
            body = {"scene": {"location": "Old Manor"}}
        elif path == "/api/chats/1/attire":
            body = {"Alice": SLICES["kitchen"]["occupants"][0]["attire"]}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    return seen


def _open_story(page: Page, ui_base_url: str) -> list[str]:
    seen = _mount(page)
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")
    return seen


def test_the_world_button_opens_on_the_room_tree_and_the_players_room(
        page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _open_story(page, ui_base_url)

    page.locator("#b-world").click()
    modal = page.locator("#modal")
    expect(modal).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("World state")
    # Browse is the first tab and the one that opens.
    expect(modal.locator(".lore-inspector-tabs button.on")).to_have_text("Browse")
    # The tree: the cast's rooms with the occupants beside them, the plan's
    # rooms badged, the retired ids folded away, the interior nested.
    tree = modal.locator(".wb-tree")
    expect(tree).to_contain_text("Where the cast stands")
    expect(tree.locator(".wb-room[data-room=kitchen]")).to_contain_text("Alice")
    expect(tree.locator(".wb-room[data-room=attic] .badge")).to_have_text("Planned")
    expect(tree.locator(".wb-nested .wb-room[data-room=console_room]")).to_have_count(1)
    expect(tree.locator("details.wb-retired")).not_to_have_attribute("open", "")
    expect(tree.locator(".wb-room[data-room=old_wing]")).to_be_hidden()
    # The card: the player's room, its prose, its exits.
    card = modal.locator(".wb-card")
    expect(tree.locator(".wb-room.on")).to_have_attribute("data-room", "kitchen")
    expect(card).to_contain_text("A rustic kitchen with a heavy oak table.")
    expect(card).to_contain_text("Move here")
    assert page_errors == []


def test_an_exit_walks_to_the_far_room(page: Page, ui_base_url: str) -> None:
    seen = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    card = modal.locator(".wb-card")
    expect(card).to_contain_text("A rustic kitchen")

    card.locator(".wb-exit .wb-link", has_text="Hallway").click()
    expect(card).to_contain_text("A long, dim hallway.")
    expect(modal.locator(".wb-tree .wb-room.on")).to_have_attribute("data-room", "hallway")
    assert "/api/chats/1/rooms/hallway" in seen
    # A planned far room is badged on its exit row, and is still a link.
    card.locator(".wb-exit .wb-link", has_text="Kitchen").click()
    expect(card.locator(".wb-exit", has_text="Attic").locator(".badge")).to_have_text("Planned")


def test_the_raw_tab_keeps_the_world_editor(page: Page, ui_base_url: str) -> None:
    seen = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    modal.locator(".lore-inspector-tabs button", has_text="Raw JSON").click()
    textarea = modal.locator("textarea")
    expect(textarea).to_be_visible()
    expect(textarea).to_have_value(json.dumps({"scene": {"location": "Old Manor"}}, indent=2))
    expect(modal.get_by_role("button", name="Save")).to_be_visible()
    assert "/api/chats/1/world" in seen


def test_the_attire_button_opens_the_same_browser_with_the_bodies_unfolded(
        page: Page, ui_base_url: str) -> None:
    seen = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    modal = page.locator("#modal")
    expect(page.locator("#modaltitle")).to_have_text("Attire")
    body = modal.locator("details.wb-body", has_text="Alice")
    expect(body).to_have_attribute("open", "")
    expect(body).to_contain_text("apron")
    expect(body).to_contain_text("Attire is read-only here")
    # Its Raw JSON tab is the attire ledger, not the world table.
    body.locator("button.wb-link", has_text="Raw JSON").click()
    expect(modal.locator("textarea")).to_contain_text('"apron"')
    assert "/api/chats/1/attire" in seen and "/api/chats/1/world" not in seen
