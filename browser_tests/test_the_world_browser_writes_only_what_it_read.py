"""The World Browser writes only what it read, and Undo only where it was made.

Audit 2026-11-01 (`frontend_settings_world` F1, F2, F6), in a real browser
over the same mocked API `test_world_browser.py` builds:

* F2 -- the room card writes a room's exits, anchors and parts as WHOLE
  lists, and `PATCH /rooms/{id}` replaces the room's list with what it is
  sent (`web/world_routes.py` `_apply_exits`, `_apply_anchors`). A card drawn
  before a beat committed sent the beat's room back without the beat's
  doorway: `_apply_exits` then removed that doorway from BOTH rooms and
  popped its passage record, under "Saved.". The same for an attire edit,
  which sends one body's whole entry. Each list write now reads the room
  (or the ledger) again first and refuses, in words, when it moved.
* F1 -- Undo kept a whole-field snapshot and re-issued it through whichever
  room was selected when it was clicked: over a card edit made after the
  drag, and -- through the Bodies tab's room link -- onto another room.
* F6 -- the card's "Add exit" defaulted to the alphabetically first barrier,
  `bars`, which nobody can walk through; the map's wall form chose `open`.
"""

from __future__ import annotations

import copy
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_world_browser import ALICE_ATTIRE, SLICES, _open_map, _open_story

CHANGED = "This room changed since the card was drawn"


def _a_beat_writes_the_room(page: Page, rid: str, mutate) -> None:
    """From now on, a read of the room's slice answers with `mutate(slice)`:
    a beat, another window or the Writers' Room wrote the room after the
    card was drawn. Registered after the base mock, so it answers first;
    everything else falls through to the base mock."""
    fresh = copy.deepcopy(SLICES[rid])
    mutate(fresh)

    def handle(route) -> None:
        if route.request.method == "GET" and \
                urlparse(route.request.url).path == f"/api/chats/1/rooms/{rid}":
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(fresh))
        else:
            route.fallback()

    page.route("**/api/chats/1/rooms/**", handle)


def test_an_anchor_edit_is_refused_when_the_room_changed_since_the_card_was_drawn(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    hearth = card.locator(".wb-anchor[data-anchor=hearth]")
    expect(hearth).to_have_count(1)

    # A beat hangs a lamp hook on the north wall while the card sits open.
    _a_beat_writes_the_room(page, "kitchen", lambda s: s["record"]["anchors"].update(
        {"lamp_hook": {"desc": "a lamp hook", "dir": "n"}}))
    hearth.locator("select").nth(1).select_option("full")          # its height

    expect(page.locator("#toasts")).to_contain_text(CHANGED)
    # Nothing was sent: the stale map would have deleted the hook.
    assert not [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]], writes
    # The card is drawn again from what the room now holds.
    expect(card.locator(".wb-anchor[data-anchor=lamp_hook]")).to_have_count(1)


def test_an_exit_edit_is_refused_when_a_beat_built_a_doorway_since(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    hallway = card.locator(".wb-exit[data-exit=hallway]").first
    expect(hallway).to_be_visible()

    def built_a_cellar_door(s: dict) -> None:
        s["record"]["adjacent"].append({"to": "garden", "barrier": "closed_door", "dir": "s"})
        s["exits"].append({"to": "garden", "name": "Garden", "barrier": "closed_door",
                           "dir": "s", "status": "live"})
    _a_beat_writes_the_room(page, "kitchen", built_a_cellar_door)
    hallway.locator("select").nth(1).select_option("ne")            # its bearing

    expect(page.locator("#toasts")).to_contain_text(CHANGED)
    assert not [w for w in writes if w[0] == "PATCH" and "exits" in w[2]], writes
    expect(card.locator(".wb-exit[data-exit=garden]").first).to_be_visible()


def test_an_unchanged_room_still_takes_the_edit(page: Page, ui_base_url: str) -> None:
    """The check is a question, not a lock: a room nobody else wrote is
    written as before, the whole list, the one field changed."""
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    card = page.locator("#modal .wb-card")
    card.locator(".wb-anchor[data-anchor=hearth] select").nth(1).select_option("full")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    patches = [w for w in writes if w[0] == "PATCH" and "anchors" in w[2]]
    assert patches[-1][2]["anchors"] == {
        "hearth": {"desc": "the hearth", "dir": "w", "height": "full"},
        "oak_table": {"desc": "the oak table"}}


def test_a_garment_edit_is_refused_when_the_body_changed_since_the_tab_was_drawn(
        page: Page, ui_base_url: str) -> None:
    _, writes = _open_story(page, ui_base_url)
    page.locator("#b-attire").click()
    body = page.locator("#modal details.wb-body[data-body=Alice]")
    legs = body.locator(".wb-region[data-region=legs]")
    expect(legs.locator(".wb-garment select")).to_have_count(1)

    # A beat takes the apron off while the tab is open.
    taken_off = copy.deepcopy(ALICE_ATTIRE)
    taken_off["regions"]["torso"]["garments"] = [
        g for g in taken_off["regions"]["torso"]["garments"] if g["name"] != "apron"]
    taken_off["wearing"] = ["silk kimono"]

    def handle(route) -> None:
        if route.request.method == "GET":
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"Alice": taken_off}))
        else:
            route.fallback()

    page.route("**/api/chats/1/attire", handle)
    legs.locator(".wb-garment select").select_option("loosened")

    expect(page.locator("#toasts")).to_contain_text("changed since the tab was drawn")
    # The stale entry would have put the apron back on.
    assert not [w for w in writes if w[1] == "/api/chats/1/attire"], writes


def test_a_card_edit_after_a_drag_takes_undo_away(page: Page, ui_base_url: str) -> None:
    """Undo re-issues the anchor map as it stood before the drag; after the
    card wrote another anchor, that map would revert the card's edit too."""
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    svg.locator(".wb-m-anchor[data-anchor=hearth]").drag_to(svg.locator(".wb-m-cell").nth(3 * 6 + 0))
    expect(page.locator("#toasts")).to_contain_text("Moved hearth to the N wall")
    expect(modal.locator(".wb-map-bar .wb-undo")).to_have_count(1)

    modal.locator(".wb-card .wb-anchor[data-anchor=oak_table] select").nth(1).select_option("waist")
    expect(page.locator("#toasts")).to_contain_text("Saved.")
    expect(modal.locator(".wb-map-bar .wb-undo")).to_have_count(0)


def test_undo_does_not_follow_the_host_into_another_room(
        page: Page, ui_base_url: str) -> None:
    """Dragged in the kitchen, then the study opened from the Bodies tab: the
    kitchen's anchor map must not be offered for the study."""
    _, writes, modal = _open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    svg.locator(".wb-m-anchor[data-anchor=hearth]").drag_to(svg.locator(".wb-m-cell").nth(3 * 6 + 0))
    expect(page.locator("#toasts")).to_contain_text("Moved hearth to the N wall")
    expect(modal.locator(".wb-map-bar .wb-undo")).to_have_count(1)

    modal.locator(".lore-inspector-tabs button", has_text="Bodies").click()
    page.locator("#modal details.wb-body[data-body=Nathan] summary .wb-link").click()
    expect(modal.locator(".wb-map-bar")).to_contain_text("Study")
    expect(modal.locator(".wb-map-bar .wb-undo")).to_have_count(0)


def test_a_new_exit_from_the_card_defaults_to_an_open_doorway(
        page: Page, ui_base_url: str) -> None:
    """One default for both add forms: the map's wall form has always chosen
    `open`; the card took the first barrier in alphabetical order, `bars`."""
    _open_story(page, ui_base_url)
    page.locator("#b-world").click()
    add = page.locator("#modal .wb-card .wb-exit.wb-add").first
    expect(add.locator("select").nth(1)).to_have_value("open")
