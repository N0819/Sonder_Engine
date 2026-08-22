"""Real-browser contracts for the WP-03 replacement application shell."""

from __future__ import annotations

import json
import re

import pytest
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
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}


def _open_shell(page: Page, ui_base_url: str, *, hash_value: str = "#/play") -> None:
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json",
            body=json.dumps(BOOTSTRAP),
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html{hash_value}")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )


def test_shell_exposes_three_destinations_and_truthful_empty_play(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    primary = page.get_by_role("navigation", name="Primary")
    expect(primary.locator("[data-core-destination]")).to_have_count(3)
    for name in ("Play", "Library", "Settings"):
        expect(primary.get_by_role("link", name=name, exact=True)).to_be_visible()

    expect(page.get_by_role("main")).to_be_visible()
    expect(page.get_by_role("heading", name="Play", level=1)).to_be_focused()
    expect(page.get_by_text("Choose a story to begin.", exact=True)).to_be_visible()
    assert page.get_by_text("Provider", exact=True).count() == 0


def test_destination_navigation_refresh_and_history_preserve_orientation(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    page.get_by_role("link", name="Library", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/library$"))
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_focused()

    page.reload()
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    expect(page).to_have_url(re.compile(r"#/library$"))
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_visible()

    page.get_by_role("link", name="Settings", exact=True).click()
    page.go_back()
    expect(page).to_have_url(re.compile(r"#/library$"))
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_visible()


def test_navigation_state_restores_valid_route_scroll_and_focus_identity(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          history.replaceState(null, "", location.pathname);
          const navigationModule = await import(
            `${base}/static/js/ui-next/navigation-state.js?release=wp03.1`
          );
          const routerModule = await import(
            `${base}/static/js/ui-next/router.js?release=wp03.1`
          );
          let record = {
            route: "#/library/characters",
            scrollRegions: {},
            focusIdentity: "",
          };
          const localState = {
            snapshot: () => ({ navigation: structuredClone(record) }),
            setRecord: (_name, value) => { record = structuredClone(value); return true; },
          };
          const region = document.createElement("div");
          region.dataset.shellScrollRegion = "workspace";
          region.style.cssText = "height:40px;overflow:auto";
          const content = document.createElement("div");
          content.style.height = "1000px";
          region.append(content);
          document.body.append(region);
          const focusTarget = document.createElement("button");
          focusTarget.dataset.focusIdentity = "story-card:17";
          document.body.append(focusTarget);

          const navigation = navigationModule.createNavigationState({
            localState,
            target: window,
            document,
          });
          const initial = navigation.prepareInitialRoute(routerModule.parseHashRoute);
          navigation.onRoute(routerModule.parseHashRoute("#/play"));
          region.scrollTop = 180;
          navigation.onRoute(routerModule.parseHashRoute("#/library"));
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          const libraryScroll = region.scrollTop;
          region.scrollTop = 72;
          navigation.onRoute(routerModule.parseHashRoute("#/play"));
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          const playScroll = region.scrollTop;
          const focused = navigation.restoreFocus("story-card:17");
          const activeIdentity = document.activeElement.dataset.focusIdentity;
          navigation.teardown();
          return {
            initial,
            locationHash: location.hash,
            libraryScroll,
            playScroll,
            focused,
            activeIdentity,
            storedRoute: record.route,
            storedFocus: record.focusIdentity,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "initial": "#/library/characters",
        "locationHash": "#/library/characters",
        "libraryScroll": 0,
        "playScroll": 180,
        "focused": True,
        "activeIdentity": "story-card:17",
        "storedRoute": "#/play",
        "storedFocus": "story-card:17",
    }


def test_shell_restores_only_a_valid_saved_route_when_url_has_no_hash(
    page: Page, ui_base_url: str
) -> None:
    page.add_init_script(
        """(() => localStorage.setItem("sonder.ui-next", JSON.stringify({
          version: 2,
          appearance: {},
          navigation: {
            route: "#/library/characters",
            scrollRegions: {},
            focusIdentity: "destination:library",
          },
          panes: {},
          drafts: {},
        })))()"""
    )
    _open_shell(page, ui_base_url, hash_value="")
    expect(page).to_have_url(re.compile(r"#/library/characters$"))
    expect(page.get_by_role("heading", name="Characters", level=1)).to_be_visible()


def test_desktop_inspector_opens_closes_pins_and_resizes_without_covering_workspace(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    _open_shell(page, ui_base_url)
    inspector = page.get_by_role("complementary", name="Story tools")
    expect(inspector).to_be_visible()

    inspector.get_by_role("button", name="Resize context panel").click()
    expect(page.locator("html")).to_have_attribute("data-inspector-size", "wide")
    inspector.get_by_role("button", name="Pin context panel").click()
    expect(page.locator("html")).to_have_attribute("data-inspector-pinned", "false")
    inspector.get_by_role("button", name="Close context panel").click()
    expect(inspector).to_be_hidden()

    opener = page.get_by_role("button", name="Open context panel")
    expect(opener).to_be_focused()
    opener.click()
    expect(inspector).to_be_visible()
    expect(inspector.get_by_role("heading", name="Story tools")).to_be_focused()
    overlap = page.evaluate(
        """() => {
          const workspace = document.querySelector('[data-ui-region="workspace"]')
            .getBoundingClientRect();
          const inspector = document.querySelector('[data-ui-region="inspector"]')
            .getBoundingClientRect();
          return workspace.right - inspector.left;
        }"""
    )
    assert overlap <= 1


def test_mobile_inspector_is_a_back_owned_focus_contained_sheet(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    _open_shell(page, ui_base_url)
    opener = page.get_by_role("button", name="Open context panel")
    opener.click()
    dialog = page.get_by_role("dialog", name="Story tools")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="Close")).to_be_focused()
    assert page.locator("[data-ui-region='workspace']").evaluate(
        "node => Boolean(node.closest('[inert]'))"
    )

    page.go_back()
    expect(dialog).to_be_hidden()
    expect(opener).to_be_focused()


def test_invalid_nested_link_shows_explanation_at_its_safe_parent(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url, hash_value="#/settings/not-real")
    expect(page.get_by_role("heading", name="Settings", level=1)).to_be_visible()
    expect(page.get_by_role("status")).to_contain_text(
        "That page does not exist. Its parent area was opened instead."
    )

def test_go_to_is_keyboard_owned_and_does_not_fire_while_typing(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    page.keyboard.press("Control+K")
    dialog = page.get_by_role("dialog", name="Go To")
    expect(dialog).to_be_visible()
    search = dialog.get_by_role("searchbox", name="Find a destination")
    expect(search).to_be_focused()
    search.fill("settings")
    search.press("Enter")
    expect(page).to_have_url(re.compile(r"#/settings$"))

    typing_probe = page.locator("[data-shell-typing-probe]")
    typing_probe.focus()
    typing_probe.press("Control+K")
    expect(dialog).not_to_be_visible()


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 360, "height": 800},
        {"width": 390, "height": 844},
        {"width": 430, "height": 932},
        {"width": 768, "height": 1024},
        {"width": 844, "height": 390},
        {"width": 1024, "height": 600},
        {"width": 1024, "height": 768},
        {"width": 1280, "height": 800},
        {"width": 1440, "height": 900},
        {"width": 640, "height": 360},
    ],
)
def test_shell_matrix_has_no_horizontal_overflow_or_hidden_destination(
    page: Page, ui_base_url: str, viewport: dict[str, int]
) -> None:
    page.set_viewport_size(viewport)
    _open_shell(page, ui_base_url)

    geometry = page.evaluate(
        """() => ({
          pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          layout: document.documentElement.dataset.layoutState,
          destinations: [...document.querySelectorAll('[data-core-destination]')].map(node => ({
            name: node.dataset.coreDestination,
            width: node.getBoundingClientRect().width,
            height: node.getBoundingClientRect().height,
          })),
        })"""
    )
    assert geometry["pageOverflow"] <= 1
    assert geometry["layout"] in {"compact", "medium", "wide", "expansive"}
    assert [item["name"] for item in geometry["destinations"]] == [
        "play",
        "library",
        "settings",
    ]
    assert all(item["width"] > 0 and item["height"] >= 44 for item in geometry["destinations"])
