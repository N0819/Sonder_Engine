"""The actual drawer keeps observer, variant and raw-edit views in sync."""

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP


def test_grouped_perception_switches_observers_variants_and_edits_original_json(
        page: Page, ui_base_url: str) -> None:
    event = {"phase": "event", "order": 1, "channel": "hearing",
             "actor": "a voice", "fidelity": "partial",
             "observed": {"text": 'A voice says, "Wait."'}}
    change = {"phase": "change", "channel": "sight",
              "observed": {"text": "Her cheeks look pinker."}}
    state = {"phase": "state", "channel": "sight",
             "observed": {"text": "She is beside the door."}}
    raw = {"views": {"72": "\n".join(row["observed"]["text"] for row in [event, change, state]),
                      "player": "You hear distant footsteps."},
           "observations": {"72": [event, change, state]},
           "meta": {"retained": "original saved JSON"}}
    empty = {"events": [], "changes_noticed": [], "current_state": []}
    packets = {"72": {"events": [event], "changes_noticed": [change], "current_state": [state]},
               "player": dict(empty, unstructured_context=[
                   {"observed": {"text": raw["views"]["player"]}}])}
    old_raw = {"views": {"72": "An archived paragraph.", "player": "An older player view."}}
    old_packets = {observer: dict(empty, unstructured_context=[{"observed": {"text": text}}])
                   for observer, text in old_raw["views"].items()}
    payload = {"steps": [{"id": 1, "key": "perception_act", "label": "Perception",
                           "ord": 1, "stale": False, "variants": [
                               {"id": 1, "active": False, "content": json.dumps(old_raw),
                                "perception_packets": old_packets},
                               {"id": 2, "active": True, "content": json.dumps(raw),
                                "perception_packets": packets}]}],
               "editable": True, "resumable": False,
               "perceivers": {"72": "Mira", "player": "Rowan"}}
    writes = []

    def api(route):
        path = urlparse(route.request.url).path
        if route.request.method != "GET":
            writes.append(path)
        if path == "/api/bootstrap":
            body = BOOTSTRAP
        elif path == "/api/turns/10/pipeline":
            body = payload
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", api)
    page.goto(ui_base_url + "/static/index.html")
    page.wait_for_function("() => typeof openPipeline === 'function'")
    page.evaluate("() => openPipeline(10)")
    drawer = page.locator("#drawer")
    view = drawer.locator(".step > pre")
    expect(view).to_contain_text("Events (1)")
    expect(view).to_contain_text("Changes noticed (1)")
    expect(view).to_contain_text("Current state (1)")
    assert view.inner_text().count('A voice says, "Wait."') == 1

    drawer.get_by_role("button", name="Rowan (player)", exact=True).click()
    expect(view).to_contain_text("Additional context (1)")
    expect(view).to_contain_text("You hear distant footsteps.")
    expect(view).not_to_contain_text("Her cheeks")

    drawer.get_by_role("button", name="◀", exact=True).click()
    expect(view).to_contain_text("An older player view.")
    expect(view).not_to_contain_text("An archived paragraph.")
    drawer.get_by_role("button", name="▶", exact=True).click()
    expect(view).to_contain_text("You hear distant footsteps.")

    drawer.get_by_role("button", name="{ } JSON", exact=True).click()
    assert json.loads(view.inner_text()) == raw
    drawer.get_by_role("button", name="Mira (72)", exact=True).click()
    expect(view).to_contain_text("Changes noticed (1)")
    drawer.get_by_title("Edit JSON", exact=True).click()
    editor = page.locator("#modal textarea")
    expect(editor).to_be_visible()
    assert json.loads(editor.input_value()) == raw
    assert writes == []
