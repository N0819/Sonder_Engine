"""Real-browser contracts for the WP-03 replacement application shell."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


FIXTURES = Path(__file__).with_name("fixtures")


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
    expect(page.get_by_text("Choose a story to begin", exact=True)).to_be_visible()
    assert page.get_by_text("Provider", exact=True).count() == 0


def test_destination_navigation_refresh_and_history_preserve_orientation(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url)

    page.get_by_role("link", name="Library", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/library$"))
    expect(page.get_by_role("heading", name="Library", level=2)).to_be_focused()

    page.reload()
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    expect(page).to_have_url(re.compile(r"#/library$"))
    expect(page.get_by_role("heading", name="Library", level=2)).to_be_visible()

    page.get_by_role("link", name="Settings", exact=True).click()
    page.go_back()
    expect(page).to_have_url(re.compile(r"#/library$"))
    expect(page.get_by_role("heading", name="Library", level=2)).to_be_visible()


def test_navigation_state_restores_valid_route_scroll_and_focus_identity(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          history.replaceState(null, "", location.pathname);
          const navigationModule = await import(
            `${base}/static/js/ui-next/navigation-state.js?release=alpha98-ui13-a39372e1d8d1`
          );
          const routerModule = await import(
            `${base}/static/js/ui-next/router.js?release=alpha98-ui13-a39372e1d8d1`
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
    expect(page.get_by_role("heading", name="Library", level=2)).to_be_visible()


def test_library_to_play_transition_cannot_restore_a_removed_library_inspector(
    page: Page, ui_base_url: str
) -> None:
    _open_shell(page, ui_base_url, hash_value="#/library")
    page.get_by_role("link", name="Play", exact=True).click()

    inspector = page.get_by_role("complementary", name="Story tools")
    expect(inspector.get_by_role("heading", name="Story tools")).to_be_visible()
    expect(inspector.get_by_text("Choose a story to use Story Tools.", exact=True)).to_be_visible()
    expect(inspector.get_by_text("Select a Library row to see its usage and details.", exact=True)).to_have_count(0)


def test_story_tools_opener_keeps_icon_and_label_on_one_row(
    page: Page, ui_base_url: str,
) -> None:
    _open_shell(page, ui_base_url)
    opener = page.get_by_role("button", name="Open context panel")
    expect(opener.get_by_text("Story tools", exact=True)).to_be_visible()
    geometry = opener.evaluate(
        """node => {
          const icon = node.querySelector('.ui-icon').getBoundingClientRect();
          const label = node.querySelector('.ui-icon-label').getBoundingClientRect();
          const button = node.getBoundingClientRect();
          return {
            height: button.height,
            centerDelta: Math.abs((icon.top + icon.height / 2) - (label.top + label.height / 2)),
          };
        }"""
    )
    assert geometry["height"] <= 44
    assert geometry["centerDelta"] <= 1


def test_desktop_inspector_opens_closes_pins_and_resizes_without_covering_workspace(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    _open_shell(page, ui_base_url)
    inspector = page.get_by_role("complementary", name="Story tools")
    expect(inspector).to_be_visible()
    pin_button = inspector.get_by_role("button", name="Pin context panel")
    pin_icon = pin_button.locator("use")
    expect(pin_button).to_have_attribute("aria-pressed", "true")
    expect(pin_icon).to_have_attribute("href", "/static/assets/icons/sonder-icons.svg?release=alpha98-ui13-a39372e1d8d1#icon-pin")

    inspector.get_by_role("button", name="Resize context panel").click()
    expect(page.locator("html")).to_have_attribute("data-inspector-size", "compact")
    pin_button.click()
    expect(page.locator("html")).to_have_attribute("data-inspector-pinned", "false")
    expect(pin_button).to_have_attribute("aria-pressed", "false")
    expect(pin_icon).to_have_attribute("href", "/static/assets/icons/sonder-icons.svg?release=alpha98-ui13-a39372e1d8d1#icon-pin")
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
    expect(
        page.get_by_role("heading", name="Sonder preferences", level=1)
    ).to_be_visible()
    expect(page.locator(".ui-shell__route-notice")).to_contain_text(
        "That page does not exist. Its parent area was opened instead."
    )


def test_forbidden_bootstrap_stays_inline_without_exposing_technical_detail(
    page: Page, ui_base_url: str
) -> None:
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            status=403,
            content_type="application/json",
            body='{"detail":"private host policy detail"}',
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'failed'", timeout=10000
    )
    expect(page.get_by_text(
        "This account cannot open the replacement interface.", exact=True
    )).to_be_visible()
    expect(page.get_by_text("private host policy detail", exact=True)).to_have_count(0)
    assert page.url.endswith("#/play")


def test_long_japanese_shell_copy_and_accessibility_preset_keep_actions_reachable(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 360, "height": 800})
    messages = {
        "Play": "プレイ中の物語と現在進行中の場面を確認する場所",
        "Library": "ストーリーと登場人物と世界設定をまとめて探すライブラリ",
        "Settings": "表示や接続やメンテナンスを調整するための設定",
        "Your active story and its tools stay together here.": (
            "現在選ばれている物語と、その物語だけに関係する道具は、"
            "迷わず戻れるようにこの場所へまとめて表示されます。"
        ),
        "Choose a story to begin.": "始めるストーリーをライブラリから選んでください。",
        "Go To": "目的の場所へすばやく移動",
        "Find a destination": "移動したい画面や機能の名前を入力して検索",
    }
    bootstrap = {**BOOTSTRAP, "ui_language": "ja", "ui_messages": messages}
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(bootstrap)
        ),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/play")
    assert response is not None and response.ok
    page.wait_for_function(
        "document.documentElement.dataset.uiNextState === 'ready'", timeout=10000
    )
    page.evaluate(
        """() => {
          const root = document.documentElement;
          root.dataset.a11yHighContrast = "true";
          root.dataset.a11ySolid = "true";
          root.dataset.a11yStrongFocus = "true";
          root.dataset.a11yLargeUi = "true";
          root.dataset.a11yLargeProse = "true";
          root.dataset.a11yRoomyTargets = "true";
          root.dataset.a11yReducedMotion = "true";
        }"""
    )
    expect(page.locator("html")).to_have_attribute("lang", "ja")
    expect(page.get_by_role(
        "heading", name="プレイ中の物語と現在進行中の場面を確認する場所", level=1
    )).to_be_visible()
    geometry = page.evaluate(
        """() => ({
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          targets: [...document.querySelectorAll('[data-core-destination]')]
            .map(node => node.getBoundingClientRect().height),
        })"""
    )
    assert geometry["overflow"] <= 1
    assert all(size >= 50 for size in geometry["targets"])
    opener = page.get_by_role("button", name="目的の場所へすばやく移動", exact=True)
    expect(opener).to_be_visible()
    compact_geometry = page.evaluate(
        """() => {
          const opener = document.querySelector('[data-shell-go-to]').getBoundingClientRect();
          const destinations = [...document.querySelectorAll('[data-core-destination]')];
          const labels = destinations.map(node => node.querySelector('.ui-shell__destination-label'));
          return {
            openerTop: opener.top,
            openerBottom: opener.bottom,
            navigationTop: document.querySelector('.ui-shell__navigation').getBoundingClientRect().top,
            labelHeights: labels.map(node => node.getBoundingClientRect().height),
            labelScrollHeights: labels.map(node => node.scrollHeight),
          };
        }"""
    )
    assert compact_geometry["openerBottom"] <= compact_geometry["navigationTop"]
    assert compact_geometry["openerTop"] < 96
    assert max(compact_geometry["labelHeights"]) <= 48
    assert page.locator(".ui-shell__destination-label").first.evaluate(
        "node => getComputedStyle(node).webkitLineClamp"
    ) == "2"
    opener.click()
    expect(page.get_by_role(
        "searchbox", name="移動したい画面や機能の名前を入力して検索"
    )).to_be_focused()

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

    page.evaluate(
        """() => {
          const input = document.createElement("input");
          input.dataset.shellTypingProbe = "true";
          input.setAttribute("aria-label", "Typing guard probe");
          document.querySelector('[data-shell-destination-view]').append(input);
        }"""
    )
    typing_probe = page.locator("[data-shell-typing-probe]")
    typing_probe.focus()
    typing_probe.press("Control+K")
    expect(dialog).not_to_be_visible()


def test_shortcut_registry_rejects_collisions_and_guards_typing_and_ime(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createShortcutRegistry } = await import(
            `${base}/static/js/ui-next/shortcuts.js?release=alpha98-ui13-a39372e1d8d1`
          );
          let calls = 0;
          let collision = null;
          const registry = createShortcutRegistry({ target: window });
          registry.register({
            owner: "core-shell",
            id: "go-to",
            combo: "mod+k",
            label: "Open Go To",
            handler: () => { calls += 1; },
            core: true,
          });
          try {
            registry.register({
              owner: "fixture-extension",
              id: "replace-go-to",
              combo: "mod+k",
              label: "Collision",
              handler: () => { calls += 100; },
            });
          } catch (error) {
            collision = { kind: error.kind, owner: error.owner, combo: error.combo };
          }
          registry.start();
          document.body.dispatchEvent(new KeyboardEvent("keydown", {
            key: "k", ctrlKey: true, bubbles: true,
          }));
          const input = document.createElement("input");
          document.body.append(input);
          input.dispatchEvent(new KeyboardEvent("keydown", {
            key: "k", ctrlKey: true, bubbles: true,
          }));
          document.body.dispatchEvent(new KeyboardEvent("keydown", {
            key: "k", ctrlKey: true, bubbles: true, isComposing: true,
          }));
          const entries = registry.entries();
          registry.stop();
          document.body.dispatchEvent(new KeyboardEvent("keydown", {
            key: "k", ctrlKey: true, bubbles: true,
          }));
          return { calls, collision, entries };
        }""",
        ui_base_url,
    )
    assert result == {
        "calls": 1,
        "collision": {
            "kind": "shortcut-collision",
            "owner": "core-shell",
            "combo": "mod+k",
        },
        "entries": [
            {
                "owner": "core-shell",
                "id": "go-to",
                "combo": "mod+k",
                "label": "Open Go To",
                "core": True,
            }
        ],
    }


def test_go_to_remains_touch_reachable_on_compact_shell(
    page: Page, ui_base_url: str
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    _open_shell(page, ui_base_url)
    opener = page.get_by_role("button", name="Go To", exact=True)
    expect(opener).to_be_visible()
    assert opener.evaluate("node => node.getBoundingClientRect().height") >= 44
    geometry = page.evaluate(
        """() => {
          const opener = document.querySelector('[data-shell-go-to]').getBoundingClientRect();
          const navigation = document.querySelector('.ui-shell__navigation').getBoundingClientRect();
          return { openerTop: opener.top, openerBottom: opener.bottom, navigationTop: navigation.top };
        }"""
    )
    assert geometry["openerTop"] < 96
    assert geometry["openerBottom"] <= geometry["navigationTop"]
    opener.click()
    expect(page.get_by_role("dialog", name="Go To")).to_be_visible()


def test_v1_extension_mounts_navigates_calls_fails_safely_and_unmounts(
    page: Page, ui_base_url: str
) -> None:
    calls: list[dict[str, object]] = []
    page.route(
        "**/api/chats",
        lambda route: route.fulfill(content_type="application/json", body="[]"),
    )

    def serve_extension_call(route):
        calls.append(
            {
                "method": route.request.method,
                "url": route.request.url,
                "body": route.request.post_data_json,
            }
        )
        route.fulfill(content_type="application/json", body='{"ok":true}')

    page.route("**/api/extensions/fixture-v1/x/seen", serve_extension_call)
    _open_shell(page, ui_base_url)
    source = (FIXTURES / "ui_v1_extension.js").read_text(encoding="utf-8")
    page.evaluate(
        """source => {
          window.Sonder._begin("fixture-v1");
          (0, eval)(source);
          window.Sonder._end();
        }""",
        source,
    )

    page.get_by_role("button", name="Go To", exact=True).click()
    search = page.get_by_role("searchbox", name="Find a destination")
    search.fill("Fixture view")
    search.press("Enter")
    expect(page).to_have_url(
        re.compile(
            r"#/settings/add-ons\?extension=fixture-v1&kind=legacy-view&view=fixture-view$"
        )
    )
    mounted = page.get_by_role("region", name="Fixture view")
    expect(mounted).to_have_text("Fixture view mounted")

    page.evaluate("async () => window.Sonder.emit('turn:done', { turn: 9 })")
    assert calls == [
        {
            "method": "POST",
            "url": f"{ui_base_url}/api/extensions/fixture-v1/x/seen",
            "body": {"turn": 9},
        }
    ]

    page.evaluate(
        """() => {
          window.Sonder._begin("broken-view");
          window.Sonder.registerView({
            id: "broken",
            label: "Broken view",
            render() { throw new Error("fixture render failure"); },
          });
          window.Sonder._end();
        }"""
    )
    page.get_by_role("button", name="Go To", exact=True).click()
    search = page.get_by_role("searchbox", name="Find a destination")
    search.fill("Broken view")
    search.press("Enter")
    expect(page.get_by_text(
        "This add-on view is unavailable. The rest of Sonder Engine is still ready.",
        exact=True,
    )).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-ui-next-state", "ready")

    page.evaluate("() => window.Sonder._unload('broken-view')")
    expect(page).to_have_url(re.compile(r"#/settings/add-ons$"))
    expect(page.get_by_text("Broken view", exact=True)).to_have_count(0)
    expect(page.get_by_role("link", name="Play", exact=True)).to_be_visible()


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
