"""The drawer's map draws the turn's outcome room (2026-10-12).

The pipeline drawer's Map panel hands the World Browser's room renderer a
context of its own, and that context had no `currentSlice`: the renderer
asks for the room's slice on every render, so the drawer only ever said
"Map unavailable". The drawer's map is read only -- no slice, and every
writer a drag or a click reaches does nothing.
"""

import copy
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP
from test_world_browser import INDEX, SLICES, _grid


def test_the_drawers_map_draws_the_outcome_room_and_writes_nothing(
        page: Page, ui_base_url: str) -> None:
    outcome = {"player_room": "kitchen", "views": {"player": "You stand in the kitchen."}}
    payload = {"steps": [{"id": 1, "key": "perception_outcome", "label": "Outcome", "ord": 1,
                           "stale": False, "variants": [
                               {"id": 1, "active": True, "content": json.dumps(outcome)}]}],
               "editable": True, "resumable": False, "perceivers": {"player": "Nathan"}}
    errors, writes = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def api(route):
        path = urlparse(route.request.url).path
        if route.request.method != "GET":
            writes.append(path)
        if path == "/api/bootstrap":
            body = BOOTSTRAP
        elif path == "/api/turns/10/pipeline":
            body = payload
        elif path.endswith("/rooms/kitchen/grid"):
            body = _grid("kitchen", copy.deepcopy(SLICES))
        elif path.endswith("/rooms"):
            body = INDEX
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", api)
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof openPipeline === 'function'")
    page.evaluate("() => openPipeline(10)")
    drawer = page.locator("#drawer")
    drawer.locator(".pipeline-map-wrap > summary").click()
    expect(drawer.locator(".pipeline-map .wb-room-map")).to_be_visible()
    expect(drawer.locator(".pipeline-map")).not_to_contain_text("Map unavailable")
    # a drag on the read-only map writes nothing
    anchor = drawer.locator(".pipeline-map .wb-m-anchor").first
    box = anchor.bounding_box()
    page.mouse.move(box["x"] + 4, box["y"] + 4)
    page.mouse.down()
    page.mouse.move(box["x"] + 60, box["y"] + 40, steps=6)
    page.mouse.up()
    assert not writes, writes
    assert not errors, errors
