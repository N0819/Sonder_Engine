"""A card fill is a proposal over what the author has TYPED, and nothing saves
it but Save.

Audit 2026-11-01 (`frontend_lorebooks_editors` F4, F5, F10), in a real
browser over a mocked API:

* F4 -- the three fill buttons reopened the editor from the STORED card plus
  the model's answer: a drive essence typed and not yet saved was replaced by
  the model's, and every unsaved edit outside the fill's own fields (a typed
  hair colour, under a psychology fill) was simply gone. The tooltip says
  "populated fields are preserved".
* F5 -- "⚡ Quick start with this greeting" PUT `character.sheet`, which after
  a fill IS the unreviewed proposal, to the reusable card; without a fill it
  wrote the sheet as opened and dropped every widget edit. The file's own
  header: "the author's ordinary Save is still what commits it".
* F10 -- "Generate character" dropped the `warnings` its route returns, the
  one card-producing surface whose browser half never showed them.
"""

from __future__ import annotations

import copy
import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

from test_ui_smoke import BOOTSTRAP

STORED = {
    "identity": {"name": "Mara", "uid": "char-mara", "aliases": [],
                 "pronouns": {"subject": "she", "object": "her", "possessive": "her"}},
    "initial_outfit": {"regions": {}},
    "simulation": {"tier": "mid", "temperature": 0.8, "offscreen_agent": False},
    "embodiment": {"visible": {"summary": "A wiry courier.", "build": "", "face": "",
                               "hair": "cropped grey", "eyes": "", "distinctive_features": []},
                   "senses": [], "scent": "", "voice": "", "latent": []},
    "psychology": {"drive": {"essence": "", "expression": "", "taboo": ""},
                   "traits": [], "values": []},
    "opening": {"first_message": "",
                "greetings": [{"greeting_id": "greet_1", "prose": "Rain on the depot roof.",
                               "extraction": None, "extractor_version": None}]},
}


def _filled(stored: dict) -> dict:
    """What `fill_character_psychology` answers: the STORED card, gaps filled."""
    out = copy.deepcopy(stored)
    out["psychology"]["drive"] = {"essence": "MODEL: to be needed",
                                  "expression": "MODEL: takes every run nobody wants",
                                  "taboo": "MODEL: never opens a parcel"}
    return out


def _mount(page: Page, writes: list) -> None:
    bootstrap = {**BOOTSTRAP,
                 "characters": [{"id": 5, "name": "Mara", "sheet": json.dumps(STORED)}],
                 "personas": [{"id": 1, "name": "Nathan", "sheet": "{}"}]}

    def handle(route) -> None:
        request = route.request
        path = urlparse(request.url).path
        payload = json.loads(request.post_data) if request.post_data else {}
        if request.method != "GET":
            writes.append((request.method, path, payload))
        if path == "/api/bootstrap":
            body = bootstrap
        elif path == "/api/characters/5/fill_psychology":
            body = {"sheet": _filled(STORED), "warnings": []}
        elif path == "/api/characters/5/fill_appearance":
            # REPLACES the body: the model returned a hair and an outfit and
            # left the face out, so the server carried the stored face over.
            body = copy.deepcopy(STORED)
            body["embodiment"]["visible"]["hair"] = "MODEL: braided black"
            body["initial_outfit"] = {"regions": {"torso": {"garments": [
                {"name": "oilskin coat", "state": "worn"}], "beneath": ""}}}
            body = {"sheet": body, "warnings": []}
        elif path == "/api/characters/generate":
            body = {"id": 7, "sheet": {"identity": {"name": "Tam"}},
                    "warnings": ["Tam's psychology.drive is empty: the character will want nothing."]}
        else:
            body = {"ok": True} if request.method != "GET" else {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/**", handle)


def _field(page: Page, label: str):
    return page.locator("#modal .ff", has_text=label).locator("input, textarea").first


def _open_editor(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/static/index.html")
    expect(page.locator("#send")).to_be_visible()
    page.evaluate("() => charEditor(S.boot.characters[0])")
    expect(page.locator("#modaltitle")).to_have_text("Edit character — Mara")


def _fill_psychology(page: Page) -> None:
    page.get_by_role("button", name="✨ Fill psychology gaps").click()
    overlay = page.locator(".confirm-overlay")
    overlay.locator("input").fill("a courier who hates being idle")
    overlay.get_by_role("button", name="OK").click()
    expect(page.locator("#toasts")).to_contain_text("Missing psychology fields filled")


def test_a_psychology_fill_keeps_what_was_typed_and_fills_only_the_gaps(
        page: Page, ui_base_url: str) -> None:
    writes: list = []
    _mount(page, writes)
    _open_editor(page, ui_base_url)
    _field(page, "Drive — essence").fill("to outrun the flood")
    _field(page, "Hair").fill("shaved")                 # outside the fill's fields
    _fill_psychology(page)

    # The typed essence is kept; the empty expression is filled; the typed
    # hair -- which the fill never touches -- is still what was typed.
    expect(_field(page, "Drive — essence")).to_have_value("to outrun the flood")
    expect(_field(page, "Drive — expression")).to_have_value("MODEL: takes every run nobody wants")
    expect(_field(page, "Hair")).to_have_value("shaved")
    # Nothing was written: the proposal is the author's to review.
    assert not [w for w in writes if w[0] == "PUT"], writes


def test_quick_start_never_saves_a_fills_proposal(page: Page, ui_base_url: str) -> None:
    writes: list = []
    _mount(page, writes)
    _open_editor(page, ui_base_url)
    _fill_psychology(page)
    page.get_by_role("button", name="⚡ Quick start with this greeting").click()
    expect(page.locator("#toasts")).to_contain_text("Save")
    assert not [w for w in writes if w[0] == "PUT"], writes


def test_quick_start_from_an_unedited_card_still_saves_its_greetings(
        page: Page, ui_base_url: str) -> None:
    writes: list = []
    _mount(page, writes)
    _open_editor(page, ui_base_url)
    page.get_by_role("button", name="⚡ Quick start with this greeting").click()
    expect(page.locator("#modaltitle")).to_have_text("Quick start — Mara")
    put = next(w for w in writes if w[:2] == ("PUT", "/api/characters/5"))
    assert put[2]["sheet"]["psychology"]["drive"]["essence"] == ""
    assert put[2]["sheet"]["opening"]["first_message"] == "Rain on the depot roof."


def test_a_generated_character_shows_its_card_warnings(page: Page, ui_base_url: str) -> None:
    writes: list = []
    _mount(page, writes)
    page.goto(f"{ui_base_url}/static/index.html")
    expect(page.locator("#send")).to_be_visible()
    page.evaluate("() => generateModal('character')")
    page.locator("#modal textarea").fill("a ferryman")
    page.locator("#modal").get_by_role("button", name="Generate").click()
    expect(page.locator("#toasts")).to_contain_text("psychology.drive is empty")


def test_a_body_fill_replaces_the_body_and_keeps_the_rest_of_the_form(
        page: Page, ui_base_url: str) -> None:
    writes: list = []
    _mount(page, writes)
    _open_editor(page, ui_base_url)
    _field(page, "Drive — essence").fill("to outrun the flood")    # not the body's
    _field(page, "Face").fill("rain-scarred")                       # left out by the model
    page.get_by_role("button", name="✨ Fill body & clothing").click()
    overlay = page.locator(".confirm-overlay")
    overlay.locator("input[type=text]").fill("weathered")
    overlay.get_by_role("button", name="OK").click()
    expect(page.locator("#toasts")).to_contain_text("Body and clothing generated")

    expect(_field(page, "Hair")).to_have_value("MODEL: braided black")   # replaced
    expect(_field(page, "Face")).to_have_value("rain-scarred")          # typed, kept
    expect(_field(page, "Drive — essence")).to_have_value("to outrun the flood")
    assert not [w for w in writes if w[0] == "PUT"], writes
