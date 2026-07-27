"""Behavioral smoke tests for the browser-global, no-bundler frontend."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "providers": [],
    "provider_presets": {},
    "roles": [],
    "sampler_keys": [],
    "default_samplers": {},
    "lore_categories": [],
    "lorebook_types": [],
    "memory_categories": [],
    "memory_provenance": [],
    "agent_models": {},
    "max_output_tokens": {},
    "reasoning_effort": {},
    "reasoning_effort_levels": [],
    "openrouter_routing": {},
    "max_output_tokens_bounds": {},
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "chats": [],
    "nsfw_enabled": False,
    "image_model": None,
    "backdrops_enabled": False,
    "auto_promote": True,
    "default_prompts": {},
    "prompt_presets": {},
    "active_preset": None,
    "lorebook_link_types": [],
}


def _chat_payload(chat_id: int, name: str, prose: str) -> dict:
    return {
        "chat": {"id": chat_id, "name": name},
        "participants": [],
        "turns": [{
            "id": chat_id * 10,
            "idx": 0,
            "player_input": "",
            "prose": prose,
            "stale": False,
            "frame_id": None,
        }],
        "lorebook": None,
        "lorebooks": [],
        "frames": [],
    }


def _mock_api(page: Page, bootstrap: dict, chats: dict[int, dict] | None = None) -> None:
    chats = chats or {}

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body = bootstrap
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        elif path.startswith("/api/chats/") and path.count("/") == 3:
            body = chats.get(int(path.rsplit("/", 1)[1]), {})
        else:
            body = {}
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/**", handle)


def _defer_api_paths(page: Page, paths: list[str]) -> None:
    """Hold selected fetches until the test resolves them out of order."""

    page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          const paths = %s;
          window.__pendingApi = Object.fromEntries(paths.map(path => [path, []]));
          window.__resolveApi = (path, body) => {
            const resolve = window.__pendingApi[path].shift();
            if (!resolve) throw new Error("No pending API request for " + path);
            resolve(new Response(JSON.stringify(body), {
              status: 200,
              headers: {"Content-Type": "application/json"},
            }));
          };
          window.fetch = (url, options) => {
            const path = new URL(url, window.location.href).pathname;
            if (Object.hasOwn(window.__pendingApi, path)) {
              return new Promise(resolve => window.__pendingApi[path].push(resolve));
            }
            return originalFetch(url, options);
          };
        })();
        """ % json.dumps(paths)
    )


def _wait_pending(page: Page, path: str) -> None:
    page.wait_for_function(
        "path => window.__pendingApi[path].length > 0",
        arg=path,
    )


def _resolve(page: Page, path: str, body: dict) -> None:
    page.evaluate(
        "args => window.__resolveApi(args.path, args.body)",
        {"path": path, "body": body},
    )


def _install_deferred_stream(page: Page, path: str) -> None:
    """Return one real ReadableStream whose final chunks the test controls."""

    page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          const streamPath = %s;
          window.__streamStarted = false;
          window.__finishStream = null;
          window.fetch = (url, options) => {
            const path = new URL(url, window.location.href).pathname;
            if (path !== streamPath) return originalFetch(url, options);
            const encoder = new TextEncoder();
            return Promise.resolve(new Response(new ReadableStream({
              start(controller) {
                window.__streamStarted = true;
                controller.enqueue(encoder.encode(JSON.stringify({
                  type: "step_start",
                  key: "director_interpret",
                  label: "Director · interpret",
                }) + "\\n"));
                window.__finishStream = () => {
                  controller.enqueue(encoder.encode(JSON.stringify({
                    type: "step",
                    key: "director_interpret",
                    label: "Director · interpret",
                    content: {flow: {}},
                  }) + "\\n"));
                  controller.enqueue(encoder.encode(JSON.stringify({
                    type: "done",
                    turn_id: 11,
                  }) + "\\n"));
                  controller.close();
                };
              },
            }), {
              status: 200,
              headers: {"Content-Type": "application/x-ndjson"},
            }));
          };
        })();
        """ % json.dumps(path)
    )


def test_appearance_choice_survives_a_reload(page: Page, ui_base_url: str) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    _mock_api(page, BOOTSTRAP)

    page.goto(f"{ui_base_url}/static/index.html")
    expect(page.locator("#send")).to_be_visible()
    expect(page.locator("#sidelist")).to_contain_text("No stories yet")

    page.locator("#b-theme").click()
    expect(page.locator("#modal")).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("Appearance")
    page.get_by_role("button", name="Use Tavern theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "tavern")

    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "tavern")
    assert page_errors == []


def test_latest_story_navigation_wins_out_of_order_responses(
    page: Page,
    ui_base_url: str,
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "chats": [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}],
    }
    _defer_api_paths(page, ["/api/chats/1", "/api/chats/2"])
    _mock_api(page, bootstrap)
    page.goto(f"{ui_base_url}/static/index.html")

    page.get_by_label("Open First").click()
    _wait_pending(page, "/api/chats/1")
    page.get_by_label("Open Second").click()
    _wait_pending(page, "/api/chats/2")

    _resolve(page, "/api/chats/2", _chat_payload(2, "Second", "second prose"))
    expect(page.locator("#chatname")).to_have_text("Second")
    expect(page.locator("#msgs")).to_contain_text("second prose")

    _resolve(page, "/api/chats/1", _chat_payload(1, "First", "stale first prose"))
    page.wait_for_timeout(50)
    expect(page.locator("#chatname")).to_have_text("Second")
    expect(page.locator("#msgs")).not_to_contain_text("stale first prose")
    expect(page.get_by_label("Open Second")).to_have_attribute(
        "aria-current",
        "true",
    )


def test_story_switch_closes_and_rejects_an_old_relationship_modal(
    page: Page,
    ui_base_url: str,
) -> None:
    bootstrap = {
        **BOOTSTRAP,
        "chats": [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}],
    }
    chats = {
        1: _chat_payload(1, "First", "first prose"),
        2: _chat_payload(2, "Second", "second prose"),
    }
    relationship_path = "/api/chats/1/characters/9/relationships"
    _defer_api_paths(page, [relationship_path])
    _mock_api(page, bootstrap, chats)
    page.goto(f"{ui_base_url}/static/index.html")

    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")
    page.evaluate("relationshipModal({id: 9, name: 'Ada'}, 1)")
    _wait_pending(page, relationship_path)
    expect(page.locator("#modal")).to_be_visible()
    expect(page.locator("#modaltitle")).to_have_text("Relationships — Ada")

    # The modal backdrop intentionally blocks sidebar pointer events. Exercise
    # the navigation entry point directly, as branch/import flows do.
    page.evaluate("() => openChat(2)")
    expect(page.locator("#chatname")).to_have_text("Second")
    expect(page.locator("#modal")).to_be_hidden()

    _resolve(page, relationship_path, {
        "Old Story Person": {
            "trust": 0.7,
            "familiarity": 0.4,
            "emotional_valence": 0.5,
            "fear": 0,
        },
    })
    page.wait_for_timeout(50)
    expect(page.locator("#modal")).to_be_hidden()
    expect(page.locator("body")).not_to_contain_text("Old Story Person")


def test_streamed_turn_shows_progress_and_cleans_up_after_completion(
    page: Page,
    ui_base_url: str,
) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    bootstrap = {
        **BOOTSTRAP,
        "chats": [{"id": 1, "name": "First"}],
    }
    chats = {1: _chat_payload(1, "First", "settled prose")}
    _install_deferred_stream(page, "/api/chats/1/turns")
    _mock_api(page, bootstrap, chats)
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")

    page.get_by_label("Story input").fill("Open the door.")
    page.locator("#send").click()
    page.wait_for_function("() => window.__streamStarted")

    expect(page.locator("#stop")).to_be_visible()
    expect(page.locator("#send")).to_be_disabled()
    expect(page.locator("#turnstatus")).to_be_visible()
    expect(page.locator("#turnstatus-phase")).to_have_text(
        "Reading what you did"
    )
    expect(page.get_by_label("Story input")).to_have_value("")

    page.evaluate("() => window.__finishStream()")

    expect(page.locator("#stop")).to_be_hidden()
    expect(page.locator("#send")).to_be_enabled()
    expect(page.locator("#turnstatus")).to_be_hidden()
    expect(page.locator("#msgs")).to_contain_text("settled prose")
    assert page_errors == []
