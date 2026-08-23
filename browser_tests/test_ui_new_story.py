"""Real-browser contracts for the WP09 guided New Story replacement."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [],
    "agent_models": {},
    "language_packs": [
        {"id": "en", "name": "English", "native_name": "English", "story": True}
    ],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _open(
    page: Page, ui_base_url: str, *, width: int = 1440, bootstrap: dict | None = None
) -> None:
    page.set_viewport_size({"width": width, "height": 900 if width > 700 else 844})
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(bootstrap or BOOTSTRAP)
        ),
    )
    page.route(
        "**/api/library?*",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(
                {
                    "items": [],
                    "facets": {"types": {}, "scopes": {}},
                    "page": {"offset": 0, "limit": 100, "returned": 0, "total": 0},
                    "query": {},
                }
            ),
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/library")
    assert response is not None and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")


def _open_wizard(page: Page) -> None:
    page.get_by_role("button", name="New story", exact=True).first.click()
    expect(page.get_by_role("dialog", name="New story")).to_be_visible()


def test_lived_location_request_normalizes_character_routes(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    payload = page.evaluate(
        """async () => {
          const module = await import('/static/js/ui-next/lived-location.js?release=alpha98-ui2-3f44d1cc71ed');
          return module.buildLivedLocationRequest({
            enabled: true,
            brief: '  A crowded orbital customs station  ',
            horizonHours: 720,
            characterHistories: [{ key: 'saved:9', mode: 'resident', brief: '  Two years on customs duty  ' }],
          }, { resolveCharacterId: key => key === 'saved:9' ? 9 : null });
        }"""
    )
    assert payload == {
        "enabled": True,
        "brief": "A crowded orbital customs station",
        "horizon_hours": 720,
        "active_tail_hours": 96,
        "generate_history": True,
        "character_histories": [
            {"char_id": 9, "mode": "resident", "brief": "Two years on customs duty"}
        ],
    }


def test_new_story_ports_reference_three_route_choice_without_provider(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    _open_wizard(page)

    close = page.get_by_role("button", name="Close New story")
    assert close.locator("use").get_attribute("href").endswith("#icon-close")
    expect(page.get_by_role("heading", name="Choose how to begin", level=2)).to_be_visible()
    expect(page.get_by_role("button", name="Describe a story")).to_be_visible()
    expect(page.get_by_role("button", name="Use my Library")).to_be_visible()
    expect(page.get_by_role("button", name="Start blank")).to_be_visible()
    expect(page.get_by_text("Recommended", exact=True)).to_be_visible()
    assert page.locator(".ui-new-story__routes").evaluate(
        "node => node.scrollWidth - node.clientWidth"
    ) == 0


def test_start_blank_creates_an_ordinary_story_without_ai(
    page: Page, ui_base_url: str
) -> None:
    writes: list[dict[str, object]] = []

    def create(route) -> None:
        writes.append(route.request.post_data_json)
        route.fulfill(content_type="application/json", body=json.dumps({"id": 41, "name": "Quiet Roads"}))

    page.route("**/api/chats", create)
    _open(page, ui_base_url)
    _open_wizard(page)

    page.get_by_role("button", name="Start blank").click()
    page.get_by_label("Story name").fill("Quiet Roads")
    page.get_by_label("Opening situation").fill("Rain gathers on an empty station platform.")
    page.get_by_role("button", name="Review story").click()
    expect(page.get_by_role("heading", name="Review your story", level=2)).to_be_visible()
    expect(page.get_by_text("No AI generation selected", exact=True)).to_be_visible()
    page.get_by_role("button", name="Create story").click()

    expect(page).to_have_url(f"{ui_base_url}/static/ui-next.html#/play?chat=41")
    assert writes == [
        {
            "name": "Quiet Roads",
            "scenario": "Rain gathers on an empty station platform.",
            "language": "en",
        }
    ]


def test_blank_story_can_prepare_a_lived_location(
    page: Page, ui_base_url: str
) -> None:
    generated: list[dict[str, object]] = []
    page.route(
        "**/api/chats",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps({"id": 41})
        ),
    )
    page.route(
        "**/api/chats/41/charters/generate",
        lambda route: (
            generated.append(route.request.post_data_json),
            route.fulfill(
                content_type="application/json",
                body=json.dumps({"charters": {"items": {}}, "warnings": []}),
            ),
        ),
    )
    _open(page, ui_base_url)
    _open_wizard(page)
    page.get_by_role("button", name="Start blank").click()
    page.get_by_label("Story name").fill("Customs Wake")
    page.get_by_text("Prepare a lived location", exact=True).click()
    page.get_by_label("Prepare a lived location").check()
    page.get_by_label("Location brief").fill("A crowded orbital customs station")
    page.get_by_label("Recent history").select_option("720")
    page.get_by_role("button", name="Review story").click()
    expect(page.get_by_text("Past month · active tail 96 hours", exact=True)).to_be_visible()
    page.get_by_role("button", name="Create story").click()
    expect(page).to_have_url(f"{ui_base_url}/static/ui-next.html#/play?chat=41")
    assert generated == [{
        "enabled": True,
        "brief": "A crowded orbital customs station",
        "horizon_hours": 720,
        "active_tail_hours": 96,
        "generate_history": True,
    }]


def test_failed_post_create_setup_deletes_the_incomplete_story(
    page: Page, ui_base_url: str
) -> None:
    requests: list[tuple[str, str]] = []
    page.route(
        "**/api/chats",
        lambda route: (
            requests.append((route.request.method, "/api/chats")),
            route.fulfill(content_type="application/json", body=json.dumps({"id": 41})),
        ),
    )
    page.route(
        "**/api/chats/41/charters/generate",
        lambda route: (
            requests.append((route.request.method, "/api/chats/41/charters/generate")),
            route.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": "unavailable"})),
        ),
    )
    page.route(
        "**/api/chats/41",
        lambda route: (
            requests.append((route.request.method, "/api/chats/41")),
            route.fulfill(content_type="application/json", body=json.dumps({"ok": True})),
        ),
    )
    _open(page, ui_base_url)
    _open_wizard(page)
    page.get_by_role("button", name="Start blank").click()
    page.get_by_label("Story name").fill("Kept Draft")
    page.get_by_text("Prepare a lived location", exact=True).click()
    page.get_by_label("Prepare a lived location").check()
    page.get_by_label("Location brief").fill("A place whose setup fails")
    page.get_by_role("button", name="Review story").click()
    page.get_by_role("button", name="Create story").click()
    expect(page.get_by_text("Sonder could not complete that action.", exact=True)).to_be_visible()
    assert requests[-1] == ("DELETE", "/api/chats/41")
    page.get_by_role("button", name="Edit").click()
    expect(page.get_by_label("Location brief")).to_have_value("A place whose setup fails")


def test_library_route_mixes_saved_persona_character_and_lore_without_ai(
    page: Page, ui_base_url: str
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "personas": [{"id": 3, "name": "Mina Vale", "sheet": "{}"}],
        "characters": [{"id": 7, "name": "Orin Pike", "sheet": "{}"}],
        "lorebooks": [{"id": 9, "name": "The Rain Atlas"}],
    }
    writes: list[tuple[str, dict[str, object]]] = []
    page.route(
        "**/api/chats",
        lambda route: (
            writes.append(("chat", route.request.post_data_json)),
            route.fulfill(content_type="application/json", body=json.dumps({"id": 51})),
        ),
    )

    def record(name: str):
        def handler(route) -> None:
            if route.request.method != "GET":
                writes.append((name, route.request.post_data_json))
                route.fulfill(content_type="application/json", body=json.dumps({"ok": True}))
                return
            route.fulfill(
                content_type="application/json",
                body=json.dumps({"chat": {"id": 51, "name": "Rain Ledger"}, "turns": []}),
            )

        return handler

    page.route("**/api/chats/51", record("persona"))
    page.route("**/api/chats/51/characters", record("character"))
    page.route("**/api/chats/51/lorebooks", record("lore"))
    _open(page, ui_base_url, bootstrap=bootstrap)
    _open_wizard(page)

    page.get_by_role("button", name="Use my Library").click()
    page.get_by_label("Story name").fill("Rain Ledger")
    page.get_by_role("button", name="Choose story material").click()
    page.get_by_label("Player persona").select_option("3")
    page.get_by_text("Orin Pike", exact=True).click()
    page.get_by_text("The Rain Atlas", exact=True).click()
    page.get_by_role("button", name="Review story").click()
    expect(page.get_by_text("Mina Vale", exact=True)).to_be_visible()
    expect(page.get_by_text("1 saved · 0 generated", exact=True)).to_be_visible()
    page.get_by_role("button", name="Create story").click()
    expect(page).to_have_url(f"{ui_base_url}/static/ui-next.html#/play?chat=51")
    assert writes == [
        ("chat", {"name": "Rain Ledger", "scenario": "", "language": "en"}),
        ("persona", {"persona_id": 3}),
        ("character", {"char_id": 7, "already_known": False}),
        ("lore", {"lorebook_id": 9}),
    ]


def test_generation_is_blocked_only_when_generation_is_selected(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    _open_wizard(page)

    page.get_by_role("button", name="Describe a story").click()
    page.get_by_role("button", name="Choose story material").click()
    expect(page.get_by_role("button", name="Review story")).to_be_enabled()
    page.get_by_label("New character description").fill("A courier with a divided loyalty.")
    expect(page.get_by_text("AI generation is unavailable.", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Review story")).to_be_disabled()
    expect(page.get_by_role("button", name="Open AI Connections")).to_be_visible()


def test_setup_draft_resumes_and_can_be_discarded(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    _open_wizard(page)
    page.get_by_role("button", name="Describe a story").click()
    page.get_by_label("Story name").fill("Recovered Name")
    page.get_by_role("button", name="Close New story").click()

    _open_wizard(page)
    expect(page.get_by_label("Story name")).to_have_value("Recovered Name")
    expect(page.get_by_text("Recovered setup draft", exact=True)).to_be_visible()
    page.get_by_role("button", name="Discard setup draft").click()
    expect(page.get_by_role("heading", name="Choose how to begin", level=2)).to_be_visible()


def test_mobile_new_story_uses_full_screen_stages_without_overflow(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url, width=390)
    _open_wizard(page)
    geometry = page.locator("[data-new-story-dialog]").evaluate(
        """node => ({
          width: node.getBoundingClientRect().width,
          viewport: document.documentElement.clientWidth,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          targets: [...node.querySelectorAll('button')].map(button => button.getBoundingClientRect().height),
        })"""
    )
    assert geometry["width"] == 390
    assert geometry["viewport"] == 390
    assert geometry["overflow"] == 0
    assert min(geometry["targets"]) >= 44


def test_generated_card_warnings_are_reviewed_before_story_creation(
    page: Page, ui_base_url: str
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "providers": [{"id": 2, "name": "Local", "kind": "openai"}],
        "agent_models": {"default": {"provider": "Local", "model": "small"}},
    }
    writes: list[str] = []
    page.route(
        "**/api/characters/generate",
        lambda route: (
            writes.append("generate"),
            route.fulfill(
                content_type="application/json",
                body=json.dumps({"id": 17, "warnings": ["Add a greeting before play."]}),
            ),
        ),
    )
    page.route(
        "**/api/chats",
        lambda route: (
            writes.append("chat"),
            route.fulfill(content_type="application/json", body=json.dumps({"id": 61})),
        ),
    )
    page.route(
        "**/api/chats/61/characters",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps({"ok": True})),
    )
    _open(page, ui_base_url, bootstrap=bootstrap)
    _open_wizard(page)
    page.get_by_role("button", name="Describe a story").click()
    page.get_by_role("button", name="Choose story material").click()
    page.get_by_label("New character description").fill("A courier with a divided loyalty.")
    page.get_by_role("button", name="Review story").click()
    page.get_by_role("button", name="Create story").click()

    expect(page.get_by_text("Generated card needs review", exact=True)).to_be_visible()
    expect(page.get_by_text("Add a greeting before play.", exact=True)).to_be_visible()
    assert writes == ["generate"]
    page.get_by_role("button", name="Create story after reviewing warnings").click()
    expect(page).to_have_url(f"{ui_base_url}/static/ui-next.html#/play?chat=61")
    assert writes == ["generate", "chat"]


def test_creation_failure_preserves_review_and_retry_input(
    page: Page, ui_base_url: str
) -> None:
    attempts = 0

    def create(route) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            route.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": "Host unavailable"}))
            return
        route.fulfill(content_type="application/json", body=json.dumps({"id": 71}))

    page.route("**/api/chats", create)
    _open(page, ui_base_url)
    _open_wizard(page)
    page.get_by_role("button", name="Start blank").click()
    page.get_by_label("Story name").fill("Kept Through Failure")
    page.get_by_role("button", name="Review story").click()
    page.get_by_role("button", name="Create story").click()

    expect(page.get_by_text("Sonder could not complete that action.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Edit").click()
    expect(page.get_by_label("Story name")).to_have_value("Kept Through Failure")
    page.get_by_role("button", name="Review story").click()
    page.get_by_role("button", name="Create story").click()
    expect(page).to_have_url(f"{ui_base_url}/static/ui-next.html#/play?chat=71")
