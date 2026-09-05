"""The World Browser in a real browser: the tree, the card, walking an exit,
the field editors, the Bodies tab's attire editor, and the Raw JSON tab that
keeps the old editors.

Fully mocked at the network boundary. What `node --check` cannot see is the
part worth testing here: that 🌍 opens on Rooms and 👕 on Bodies, that
clicking an exit re-selects the far room in the tree and re-renders the
card, that a room's light chosen from the select is PATCHed and the card
re-renders from the server's answer, that adding an exit sends this room's
full exit list and the far room then shows the doorway, that changing a
garment's state on the Bodies tab sends the WHOLE ledger with every copy of a
spanning garment carrying the new state (never narrowed, never reset), and
that the Raw JSON tab still offers the world table for hand repair.
"""

from __future__ import annotations

import copy
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP, _chat_payload


def _row(rid, name, hops, occupants=(), status="live", holder=None,
         holder_name=None, holder_room=None):
    return {"id": rid, "name": name, "status": status, "holder": holder,
            "hops": hops, "holder_name": holder_name, "holder_room": holder_room,
            "occupants": list(occupants)}


VOCAB = {
    "light": ["dark", "dim", "lit", "bright"],
    "size": ["tiny", "small", "medium", "large", "huge", "vast"],
    "exposure": ["open", "sheltered", "enclosed"],
    "barriers": ["bars", "closed_door", "membrane", "one_way_window", "open",
                 "open_door", "separated", "unknown", "wall", "window"],
    "dirs": ["n", "ne", "e", "se", "s", "sw", "w", "nw"],
    "heights": ["floor", "waist", "head", "full"],
    "footprints": ["point", "small", "large", "run"],
    "opacities": ["opaque", "see_through"],
    "regions": [{"id": "east_wing", "name": "East Wing"}],
    "attire_regions": ["head", "torso", "arms", "hands", "waist", "groin", "legs", "feet"],
    "garment_states": ["worn", "loosened", "open", "removed"],
}

# Alice's ledger AS STORED: a kimono spanning torso and legs, recorded once per
# region, and an apron on the torso alone.
KIMONO = {"name": "silk kimono", "state": "worn", "condition": "",
          "covers": ["torso", "legs"]}
ALICE_ATTIRE = {
    "wearing": ["silk kimono", "apron"], "state": ["bare at the head, arms, hands, waist, groin, feet"],
    "regions": {"torso": {"garments": [dict(KIMONO), {"name": "apron", "state": "worn",
                                                        "condition": ""}],
                          "beneath": ""},
                "legs": {"garments": [dict(KIMONO)], "beneath": ""}},
}

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
        "unreachable": [_row("garden", "Garden", None),
                        _row("crypt", "Crypt", None, status="planned")],
        "retired": [_row("old_wing", "Old Wing", None, status="retired")],
    },
    "bodies": [
        {"name": "Nathan", "kind": "player", "char_id": None, "room": "study",
         "room_name": "Study", "station": None, "pose": None, "attire": None},
        {"name": "Alice", "kind": "cast", "char_id": 9, "room": "kitchen",
         "room_name": "Kitchen", "station": {"at": "oak_table", "near": []},
         "pose": {"posture": "standing"}, "attire": ALICE_ATTIRE},
    ],
    "vocab": VOCAB,
}


def _slice(rid, name, desc, exits, occupants=(), adjacent=None, light=""):
    return {"id": rid, "name": name, "status": "live", "holder": None,
            "holder_name": None, "description": desc, "exits": exits,
            "occupants": list(occupants), "things": [], "planned_stub": None,
            "plan_here": {"planned_entities": [], "needs": [], "package_ops": []},
            "record": {"name": name, "desc": desc, "notes": "", "light": light,
                       "size": "", "exposure": "", "region": "", "anchors": {},
                       "adjacent": adjacent if adjacent is not None else [
                           {"to": x["to"], "barrier": x["barrier"]} for x in exits
                           if x["barrier"]]},
            "stationable": [{"id": "oak_table", "desc": "the oak table", "implicit": False}]}


SLICES = {
    "kitchen": _slice("kitchen", "Kitchen", "A rustic kitchen with a heavy oak table.",
                      [{"to": "hallway", "name": "Hallway", "barrier": "open",
                        "dir": None, "status": "live"},
                       {"to": "attic", "name": "Attic", "barrier": None,
                        "dir": None, "status": "planned"}],
                      [{"name": "Alice", "station": {"at": "oak_table", "near": []},
                        "attire": ALICE_ATTIRE}],
                      adjacent=[{"to": "hallway", "barrier": "open"}]),
    "hallway": _slice("hallway", "Hallway", "A long, dim hallway.",
                      [{"to": "kitchen", "name": "Kitchen", "barrier": "open",
                        "dir": None, "status": "live"}]),
    "garden": _slice("garden", "Garden", "An overgrown garden.", []),
}

POSITIONS = {
    "rooms": [], "location": "Old Manor",
    "characters": [{"id": 9, "name": "Alice", "status": "active", "room": "kitchen"},
                   {"id": 10, "name": "Bob", "status": "active", "room": "hallway"}],
    "persona": {"name": "Nathan", "room": "kitchen"},
}


def _mount(page: Page):
    """Mock the API. A write MUTATES the mocked state the way the server
    would, so the re-render after a save shows what was saved."""
    bootstrap = {**BOOTSTRAP, "chats": [{"id": 1, "name": "First"}]}
    seen: list[str] = []
    writes: list[tuple[str, str, dict]] = []
    slices = copy.deepcopy(SLICES)
    index = copy.deepcopy(INDEX)
    attire = {"Alice": copy.deepcopy(ALICE_ATTIRE)}

    def handle(route) -> None:
        request = route.request
        path = urlparse(request.url).path
        seen.append(path)
        body = {}
        if request.method in ("PATCH", "PUT") and request.post_data:
            payload = json.loads(request.post_data)
            writes.append((request.method, path, payload))
            if request.method == "PATCH" and path.startswith("/api/chats/1/rooms/"):
                rid = path.rsplit("/", 1)[1]
                room = slices[rid]
                for key in ("light", "size", "exposure", "name", "desc", "notes", "region"):
                    if key in payload:
                        room["record"][key] = payload[key]
                if "name" in payload:
                    room["name"] = payload["name"]
                if "exits" in payload:
                    room["record"]["adjacent"] = [
                        {"to": x["to"], "barrier": x["barrier"]} for x in payload["exits"]]
                    room["exits"] = [{"to": x["to"], "name": slices.get(x["to"], {}).get(
                        "name", x["to"]), "barrier": x["barrier"], "dir": x.get("dir") or None,
                        "status": "live" if x["to"] in slices else "planned"}
                        for x in payload["exits"]]
                    for x in payload["exits"]:
                        far = slices.get(x["to"])
                        if far and not any(e["to"] == rid for e in far["exits"]):
                            far["exits"].append({"to": rid, "name": room["name"],
                                                 "barrier": x["barrier"], "dir": None,
                                                 "status": "live"})
                            far["record"]["adjacent"].append({"to": rid, "barrier": x["barrier"]})
                body = room
            elif request.method == "PUT" and path == "/api/chats/1/attire":
                attire.clear()
                attire.update(payload)
                for b in index["bodies"]:
                    if b["name"] in attire:
                        b["attire"] = attire[b["name"]]
                body = {"ok": True}
            else:
                body = {"ok": True}
        elif path == "/api/bootstrap":
            body = bootstrap
        elif path == "/api/chats/1":
            body = _chat_payload(1, "First", "settled prose")
        elif path == "/api/chats/1/vitals":
            body = {"enabled": False, "bodies": []}
        elif path == "/api/chats/1/rooms":
            body = index
        elif path.startswith("/api/chats/1/rooms/"):
            body = slices[path.rsplit("/", 1)[1]]
        elif path == "/api/chats/1/positions":
            body = POSITIONS
        elif path == "/api/chats/1/world":
            body = {"scene": {"location": "Old Manor"}}
        elif path == "/api/chats/1/attire":
            body = attire
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    return seen, writes


def _open_story(page: Page, ui_base_url: str):
    seen, writes = _mount(page)
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")
    return seen, writes


def test_the_world_button_opens_on_the_room_tree_and_the_players_room(
        page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _open_story(page, ui_base_url)

    page.locator("#b-world").click()
    modal = page.locator("#modal")
    expect(modal).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("World state")
    # Rooms is the first tab and the one 🌍 opens.
    expect(modal.locator(".lore-inspector-tabs button.on")).to_have_text("Rooms")
    expect(modal.locator(".lore-inspector-tabs button")).to_have_text(["Rooms", "Bodies", "Raw JSON"])
    # The tree: the cast's rooms with the occupants beside them, the plan's
    # rooms badged, the retired ids folded away, the interior nested.
    tree = modal.locator(".wb-tree")
    expect(tree).to_contain_text("Where the cast stands")
    expect(tree.locator(".wb-room[data-room=kitchen]")).to_contain_text("Alice")
    expect(tree.locator(".wb-room[data-room=attic] .badge")).to_have_text("Planned")
    expect(tree.locator(".wb-nested .wb-room[data-room=console_room]")).to_have_count(1)
    expect(tree.locator("details.wb-retired")).not_to_have_attribute("open", "")
    expect(tree.locator(".wb-room[data-room=old_wing]")).to_be_hidden()
    # The card: the player's room, its prose in an editor, its exits.
    card = modal.locator(".wb-card")
    expect(tree.locator(".wb-room.on")).to_have_attribute("data-room", "kitchen")
    expect(card.locator("textarea").first).to_have_value("A rustic kitchen with a heavy oak table.")
    expect(card).to_contain_text("Move here")
    assert page_errors == []


def test_an_exit_walks_to_the_far_room(page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    card = modal.locator(".wb-card")
    expect(card.locator("textarea").first).to_have_value("A rustic kitchen with a heavy oak table.")

    card.locator(".wb-exit .wb-link", has_text="Hallway").click()
    expect(card.locator("textarea").first).to_have_value("A long, dim hallway.")
    expect(modal.locator(".wb-tree .wb-room.on")).to_have_attribute("data-room", "hallway")
    assert "/api/chats/1/rooms/hallway" in seen
    # A planned far room is badged on its exit row, and is still a link.
    card.locator(".wb-exit .wb-link", has_text="Kitchen").click()
    expect(card.locator(".wb-exit", has_text="Attic").locator(".badge")).to_have_text("Planned")


def test_a_rooms_light_is_edited_through_the_select(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    light = card.locator(".wb-field", has_text="Light").locator("select")
    # The menu is the engine's set, with a blank for "unset".
    expect(light.locator("option")).to_have_text(["—", "dark", "dim", "lit", "bright"])
    light.select_option("dim")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    assert patches and patches[-1][2] == {"light": "dim"}
    # The card re-rendered from the server's answer.
    expect(card.locator(".wb-field", has_text="Light").locator("select")).to_have_value("dim")


def test_adding_an_exit_shows_the_doorway_from_both_rooms(page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    card = modal.locator(".wb-card")
    add = card.locator(".wb-exit.wb-add").first
    add.locator("select").nth(0).select_option("garden")
    add.locator("select").nth(1).select_option("closed_door")
    add.get_by_role("button", name="Add exit").click()
    expect(card.locator(".wb-exit", has_text="Garden")).to_have_count(1)
    patches = [w for w in writes if w[0] == "PATCH" and w[1] == "/api/chats/1/rooms/kitchen"]
    # This room's FULL exit list, the standing doorway kept, the new one added.
    assert patches[-1][2]["exits"] == [
        {"to": "hallway", "barrier": "open", "dir": ""},
        {"to": "garden", "barrier": "closed_door", "dir": ""}]
    # Walk through it: the far room shows the doorway back.
    card.locator(".wb-exit .wb-link", has_text="Garden").click()
    expect(card.locator("textarea").first).to_have_value("An overgrown garden.")
    expect(card.locator(".wb-exit", has_text="Kitchen")).to_have_count(1)


def test_the_raw_tab_keeps_the_world_editor(page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    modal = page.locator("#modal")
    modal.locator(".lore-inspector-tabs button", has_text="Raw JSON").click()
    textarea = modal.locator("textarea")
    expect(textarea).to_be_visible()
    expect(textarea).to_have_value(json.dumps({"scene": {"location": "Old Manor"}}, indent=2))
    expect(modal.get_by_role("button", name="Save")).to_be_visible()
    assert "/api/chats/1/world" in seen


def test_the_attire_button_opens_on_the_bodies_tab_with_the_ledgers_unfolded(
        page: Page, ui_base_url: str) -> None:
    seen, _ = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    modal = page.locator("#modal")
    expect(page.locator("#modaltitle")).to_have_text("Attire")
    expect(modal.locator(".lore-inspector-tabs button.on")).to_have_text("Bodies")
    body = modal.locator("details.wb-body[data-body=Alice]")
    expect(body).to_have_attribute("open", "")
    expect(body).to_contain_text("Cast")
    expect(body).to_contain_text("Kitchen")
    # The kimono is ONE garment shown under both regions it covers.
    torso = body.locator(".wb-region[data-region=torso]")
    legs = body.locator(".wb-region[data-region=legs]")
    expect(torso.locator(".wb-garment")).to_have_count(2)
    expect(legs.locator(".wb-garment")).to_have_count(1)
    expect(legs.locator(".wb-garment")).to_contain_text("Also:")
    # A bare region says so.
    expect(body.locator(".wb-region[data-region=head]")).to_contain_text("bare")
    # Its Raw JSON tab is the attire ledger, not the world table.
    modal.locator(".lore-inspector-tabs button", has_text="Raw JSON").click()
    expect(modal.locator("textarea")).to_contain_text('"silk kimono"')
    assert "/api/chats/1/attire" in seen and "/api/chats/1/world" not in seen


def test_changing_a_garments_state_carries_every_region_and_never_narrows_it(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    body = page.locator("#modal details.wb-body[data-body=Alice]")
    legs = body.locator(".wb-region[data-region=legs]")
    legs.locator(".wb-garment select").select_option("loosened")
    expect(page.locator("#toasts")).to_contain_text("Saved.")

    puts = [w for w in writes if w[0] == "PUT" and w[1] == "/api/chats/1/attire"]
    assert len(puts) == 1
    ledger = puts[0][2]
    # The whole ledger, this body rebuilt.
    assert set(ledger) == {"Alice"}
    regions = ledger["Alice"]["regions"]
    torso = {g["name"]: g for g in regions["torso"]["garments"]}
    legs_ = {g["name"]: g for g in regions["legs"]["garments"]}
    # Edited under the legs, loosened at the torso too: one garment.
    assert torso["silk kimono"]["state"] == "loosened"
    assert legs_["silk kimono"]["state"] == "loosened"
    assert set(torso["silk kimono"]["covers"]) == {"torso", "legs"}
    # The apron, untouched, is still worn -- not reset, not dropped.
    assert torso["apron"]["state"] == "worn"
    assert "apron" not in legs_
    # The authored note list rides along for the server to re-derive.
    assert ledger["Alice"]["state"] == ALICE_ATTIRE["state"]
    # The tab re-rendered from the saved ledger.
    expect(body.locator(".wb-region[data-region=torso]").locator(".wb-garment select").first) \
        .to_have_value("loosened")
