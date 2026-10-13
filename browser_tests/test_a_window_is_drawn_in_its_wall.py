"""A window in the room editor is a window (the owner, 2026-10-12: "windows
are being read like doors in the editor").

The server lists an edge whose barrier is a window under the grid's `windows`,
with the room it looks onto (`web.world_routes.grid_view`). The editor draws
it as a thin line in its wall -- no gap, no door bar -- and the card lists it
under Windows, with what it is, never among the exits.
"""
import copy

from playwright.sync_api import Page, expect

import test_world_browser as wb

DESC = "A paned window over the herb beds."


def _with_a_window(monkeypatch):
    slices = copy.deepcopy(wb.SLICES)
    kitchen = slices["kitchen"]
    kitchen["exits"].append({"to": "garden", "name": "Garden", "barrier": "window",
                             "dir": "s", "status": "live"})
    kitchen["record"]["adjacent"].append({"to": "garden", "barrier": "window", "dir": "s",
                                          "desc": DESC, "material": "glass"})
    index = copy.deepcopy(wb.INDEX)
    index["vocab"] = {**index["vocab"], "window_barriers": ["one_way_window", "window"]}
    monkeypatch.setattr(wb, "SLICES", slices)
    monkeypatch.setattr(wb, "INDEX", index)
    grid = wb._grid

    def windowed(rid, slices_, charter=()):
        # the server's split: an edge whose barrier is a window is a window
        view = grid(rid, slices_, charter)
        ways, windows = [], list(view.get("windows") or [])
        for d in view["doorways"]:
            if d["barrier"] in index["vocab"]["window_barriers"]:
                edge = next((e for e in slices_[rid]["record"]["adjacent"] if e["to"] == d["to"]), {})
                windows.append({**d, "desc": edge.get("desc", "")})
            else:
                ways.append(d)
        view["doorways"] = ways
        if windows:
            view["windows"] = windows
        return view

    monkeypatch.setattr(wb, "_grid", windowed)


def test_a_window_is_drawn_in_its_wall_and_listed_as_a_window(
        page: Page, ui_base_url: str, monkeypatch) -> None:
    _with_a_window(monkeypatch)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _, writes, modal = wb._open_map(page, ui_base_url)
    svg = modal.locator(".wb-room-map")
    expect(svg.locator('.wb-m-window[data-window="door:garden"]')).to_have_count(1)
    expect(svg.locator(".wb-m-doorway[data-exit=garden]")).to_have_count(0)
    expect(svg.locator(".wb-m-doorway[data-exit=hallway]")).to_have_count(1)
    card = modal.locator(".wb-card")
    expect(card.locator('.wb-window[data-window="door:garden"]')).to_contain_text("Window onto")
    expect(card.locator(".wb-exit[data-exit=garden]:not(.wb-window)")).to_have_count(0)
    box = card.locator(".wb-doorway-fields[data-doorway=garden] textarea")
    expect(box).to_have_value(DESC)
    box.fill("A paned window, one pane cracked.")
    with page.expect_response(lambda r: r.request.method == "PATCH"
                              and r.url.endswith("/api/chats/1/doorways/kitchen/garden")):
        box.blur()
    assert ("PATCH", "/api/chats/1/doorways/kitchen/garden",
            {"desc": "A paned window, one pane cracked."}) in writes
    assert not errors, errors
