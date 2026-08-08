"""Whether a room with no picture yet ever gets one commissioned.

The reported defect: rooms that already had an image showed fine, and a NEW
room stayed blank indefinitely. The asymmetry was the diagnosis -- an existing
room is served by the quick pass at BD_SETTLE_MS and never needs the paying
pass at all, so only a room that must be COMMISSIONED could be lost.

It was lost to repeat notifications about the turn the reader was already on.
`backdropOnVisibleTurn` restarted both of its clocks on every call, and the app
produces several calls per render for reasons that are not the reader moving:
`renderChat` scrolls to the bottom and then re-asserts that scroll inside a
`requestAnimationFrame` (its first `scrollHeight` is an estimate, because
`content-visibility` skips off-screen turns), and `clearBackdrop` -- which runs
precisely when the room has no picture -- strips the padding, border and
`max-width` off every `.prose` in the transcript and reflows the whole scroll
container. Each of those restarted a two-second dwell that therefore never
elapsed.

These drive the observer callback directly rather than scrolling a real
transcript: the sequence under test is "several notifications about one turn",
and producing it by scrolling would be reproducing the render's timing rather
than the rule. No network -- every route is fulfilled from the test.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page


TURN_ID = 10
SIGNATURE = "a" * 24

BOOTSTRAP = {
    "providers": [], "provider_presets": {}, "roles": [], "sampler_keys": [],
    "default_samplers": {}, "lore_categories": [], "lorebook_types": [],
    "memory_categories": [], "memory_provenance": [], "agent_models": {},
    "max_output_tokens": {}, "reasoning_effort": {},
    "reasoning_effort_levels": [], "openrouter_routing": {},
    "max_output_tokens_bounds": {}, "characters": [], "personas": [],
    "lorebooks": [], "chats": [], "nsfw_enabled": False,
    # The configuration the defect was reported under, and the one it needs:
    # switched on, with an image model set, so a miss is allowed to be paid for.
    "image_model": {"provider": 1, "model": "qwen-image-3-pro", "size": "1k"},
    "backdrops_enabled": True,
    "ambience": {"enabled": False, "source": "local", "configured": True,
                 "library": "/tmp/lib", "has_key": False,
                 "licenses": ["Creative Commons 0", "Attribution"]},
    "ambience_licenses": ["Creative Commons 0", "Attribution"],
    "auto_promote": True, "default_prompts": {}, "prompt_presets": {},
    "active_preset": None, "lorebook_link_types": [],
}


def _backdrop_miss(turn_id: int) -> dict:
    """A turn whose room has never been drawn -- the case that stayed blank."""
    return {
        "enabled": True, "configured": True,
        "room": "Dead-End Alley", "room_id": "alley_room_%d" % turn_id,
        "signature": SIGNATURE if turn_id == TURN_ID else "b%023d" % turn_id,
        "ready": False, "status": "absent", "error": None, "url": None,
        "weather": {},
    }


def _mock_backdrop_api(page: Page) -> list[str]:
    """Serve the whole API from here and record every commission."""
    posted: list[str] = []

    def handle(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/bootstrap":
            body: dict = BOOTSTRAP
        elif path.startswith("/api/turns/") and path.endswith("/backdrop"):
            turn_id = int(path.split("/")[3])
            if route.request.method == "POST":
                posted.append(path)
                body = dict(_backdrop_miss(turn_id), status="pending")
            else:
                body = _backdrop_miss(turn_id)
        elif path.startswith("/api/chats/") and path.endswith("/vitals"):
            body = {"enabled": False, "bodies": []}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    page.route("**/api/**", handle)
    return posted


def _boot(page: Page, ui_base_url: str) -> list[str]:
    posted = _mock_backdrop_api(page)
    page.goto(f"{ui_base_url}/static/index.html")
    page.wait_for_function("typeof backdropOnVisibleTurn === 'function'")
    return posted


def test_a_new_room_is_still_commissioned_when_the_render_settles(
    page: Page, ui_base_url: str
) -> None:
    """A turn the reader waited for got its commission cancelled by the render
    finishing around it, so a room with no picture yet stayed blank for good.

    The first notification armed the paying pass; the `requestAnimationFrame`
    re-scroll and the reflow from clearing the previous room's picture each
    arrived before it fired and pushed it out again. Every one of them is about
    the SAME turn, which is the reader sitting still.
    """
    posted = _boot(page, ui_base_url)

    page.evaluate(
        """turnId => {
          backdropOnVisibleTurn(turnId, { fresh: true });
          // The render settling: renderChat's rAF re-scroll, then the reflow
          // clearBackdrop() causes. Both land inside BD_SETTLE_MS and neither
          // is the reader going anywhere.
          let ticks = 0;
          const id = setInterval(() => {
            backdropOnVisibleTurn(turnId, { fresh: false });
            if (++ticks >= 12) clearInterval(id);
          }, 100);
        }""",
        TURN_ID,
    )

    page.wait_for_timeout(1500)

    assert posted, (
        "no backdrop was ever commissioned: the paying pass was postponed by "
        "every repeat notification about the turn the reader was already on"
    )
    assert all(p == "/api/turns/%d/backdrop" % TURN_ID for p in posted)


def test_scrolling_past_rooms_still_commissions_none_of_them(
    page: Page, ui_base_url: str
) -> None:
    """The property the dwell exists for, and the one a fix here could easily
    cost: a long story crosses dozens of rooms nobody stopped in, and each one
    is a paid image. Only a turn the reader SETTLES on may be paid for.
    """
    posted = _boot(page, ui_base_url)

    page.evaluate(
        """() => {
          // Different turns, in quick succession -- a flick of the wheel.
          let turn = 20;
          const id = setInterval(() => {
            backdropOnVisibleTurn(turn++, { fresh: false });
            if (turn > 32) clearInterval(id);
          }, 100);
        }"""
    )
    page.wait_for_timeout(1500)

    assert posted == [], (
        "scrolling through rooms commissioned %d image(s); passing through a "
        "room must never pay for it" % len(posted)
    )


def test_a_room_settled_on_while_scrolling_is_commissioned_after_the_dwell(
    page: Page, ui_base_url: str
) -> None:
    """The other half of the same rule: having scrolled, stopping must still
    buy the picture. A guard that ignores repeat notifications must not also
    ignore the reader arriving.
    """
    posted = _boot(page, ui_base_url)

    page.evaluate(
        """turnId => {
          let turn = 40;
          const id = setInterval(() => {
            if (turn > 44) {
              clearInterval(id);
              backdropOnVisibleTurn(turnId, { fresh: false });   // and stops
              return;
            }
            backdropOnVisibleTurn(turn++, { fresh: false });
          }, 60);
        }""",
        TURN_ID,
    )
    page.wait_for_timeout(3500)

    assert posted, "stopping on a room did not commission its picture"
    assert posted[-1] == "/api/turns/%d/backdrop" % TURN_ID
