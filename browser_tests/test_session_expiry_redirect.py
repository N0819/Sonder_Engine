"""A 401 mid-story must land the tab on /login, whichever fetch hit it.

api() has redirected 401 to /login since host auth landed, but streamPost()
-- the fetch every turn submission rides -- did not. A host session expiring
between turns therefore surfaced as a "Pipeline failed: Unauthorized" toast
on an SPA that looked signed in and wasn't: the shell is served without
auth, so nothing else on screen said the session was gone. These tests pin
the redirect on both fetch paths.
"""

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
    "chats": [{"id": 1, "name": "First"}],
    "nsfw_enabled": False,
    "image_model": None,
    "backdrops_enabled": False,
    "ambience": {"enabled": False, "source": "local", "configured": True,
                 "library": "/tmp/lib", "has_key": False,
                 "licenses": ["Creative Commons 0", "Attribution"]},
    "ambience_licenses": ["Creative Commons 0", "Attribution",
                          "Attribution NonCommercial"],
    "auto_promote": True,
    "default_prompts": {},
    "prompt_presets": {},
    "active_preset": None,
    "lorebook_link_types": [],
}

CHAT = {
    "chat": {"id": 1, "name": "First"},
    "participants": [],
    "turns": [{
        "id": 10,
        "idx": 0,
        "player_input": "",
        "prose": "settled prose",
        "stale": False,
        "frame_id": None,
    }],
    "lorebook": None,
    "lorebooks": [],
    "frames": [],
}


def _mock_api_with_expired_session(page: Page, expired_paths: set[str]) -> None:
    """Serve the mocked API, but 401 the given paths -- the middleware's
    answer once the host session cookie has expired."""

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path in expired_paths:
            route.fulfill(
                status=401,
                content_type="application/json",
                body=json.dumps({"detail": "Unauthorized"}),
            )
            return
        if path == "/api/bootstrap":
            body = BOOTSTRAP
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        elif path == "/api/chats/1":
            body = CHAT
        else:
            body = {}
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route("**/api/**", handle)


def test_turn_submission_401_redirects_to_login(
    page: Page, ui_base_url: str
) -> None:
    """The turn stream is streamPost's only caller and was the gap: before
    the fix this click produced a toast and left the dead tab in place."""
    _mock_api_with_expired_session(page, {"/api/chats/1/turns"})
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()
    expect(page.locator("#chatname")).to_have_text("First")

    page.get_by_label("Story input").fill("Open the door.")
    page.locator("#send").click()

    page.wait_for_url("**/login")


def test_plain_api_401_redirects_to_login(page: Page, ui_base_url: str) -> None:
    """Pins api()'s existing contract so the two fetch paths cannot drift
    apart again: opening a story with a dead session leaves the SPA."""
    _mock_api_with_expired_session(page, {"/api/chats/1"})
    page.goto(f"{ui_base_url}/static/index.html")
    page.get_by_label("Open First").click()

    page.wait_for_url("**/login")
