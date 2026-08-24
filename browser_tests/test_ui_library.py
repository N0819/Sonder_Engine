"""Real-browser contracts for the replacement WP-06 Library."""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import Page, expect


BOOTSTRAP = {
    "ui_language": "en",
    "ui_direction": "ltr",
    "ui_messages": {},
    "chats": [{"id": 1, "name": "The Lantern Archive"}],
    "characters": [],
    "personas": [],
    "lorebooks": [],
    "providers": [],
    "language_packs": [],
    "extensions": [],
    "extension_errors": [],
    "extension_lanes": [],
}

ITEMS = [
    {
        "kind": "story", "id": 1, "key": "story:1",
        "name": "The Lantern Archive", "summary": "A city keeps its light.",
        "subtype": "story", "created": 100.0, "reusable": False,
        "archived": False, "use_count": 1, "associations": [],
    },
    {
        "kind": "character", "id": 7, "key": "character:7",
        "name": "Mara Venn", "summary": "A careful courier.",
        "subtype": "character", "created": 90.0, "reusable": True,
        "archived": False, "use_count": 1,
        "associations": [{
            "story_id": 1, "story_name": "The Lantern Archive", "state": "active",
        }],
    },
    {
        "kind": "lore", "id": 12, "key": "lore:12",
        "name": "Quiet Roads", "summary": "Paths between old signal towers.",
        "subtype": "setting", "created": None, "reusable": True,
        "archived": False, "use_count": 0, "associations": [],
    },
]


def _projection(items=ITEMS):
    return {
        "items": items,
        "facets": {
            "types": {"story": 1, "character": 1, "persona": 0, "lore": 1},
            "scopes": {"all": 3, "story": 2, "unassigned": 1, "multiple": 0},
        },
        "page": {"offset": 0, "limit": 100, "returned": len(items), "total": len(items)},
        "query": {"scope": "all", "story_id": None, "types": [], "q": "", "sort": "name", "visibility": "active"},
    }


def _open(page: Page, ui_base_url: str, *, width: int = 1440) -> None:
    height = 900 if width >= 1400 else (1024 if width == 768 else (800 if width > 700 else 844))
    page.set_viewport_size({"width": width, "height": height})
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route(
        "**/api/library?*",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(_projection())),
    )
    response = page.goto(f"{ui_base_url}/static/ui-next.html#/library")
    assert response is not None and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    expect(page.get_by_role("heading", name="Library", level=2, exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Stories", level=2)).to_have_count(0)
    expect(page.locator("[data-library-ledger] [data-library-item]")).to_have_count(3)
    if width > 700:
        geometry = page.locator(".ui-shell").evaluate(
            """node => ({
              rail: node.querySelector('.ui-shell__navigation').getBoundingClientRect().width,
              subSidebar: Boolean(node.querySelector('.ui-library__filters')),
            })"""
        )
        expected = {"rail": 72, "subSidebar": False} if width < 1100 else {
            "rail": 192, "subSidebar": False,
        }
        assert geometry == expected
    if width > 700:
        assert page.locator(".ui-library__content").evaluate(
            "node => node.scrollWidth - node.clientWidth"
        ) == 0


def test_tablet_library_uses_one_workspace_without_a_sub_sidebar(
    page: Page, ui_base_url: str,
) -> None:
    _open(page, ui_base_url, width=768)


def test_library_has_one_workspace_for_filters_ledger_and_actions(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)

    workspace = page.locator("[data-library-workspace]")
    expect(workspace.get_by_role("heading", name="Library", level=2)).to_be_visible()
    expect(page.locator(".ui-library__filters")).to_have_count(0)
    expect(workspace.locator("[data-library-ledger]")).to_have_count(1)
    types = workspace.get_by_role("navigation", name="Library material types")
    expect(types.get_by_role("button", name="All", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(types.get_by_role("button", name="Stories", exact=True)).to_be_visible()
    expect(types.get_by_role("button", name="Characters", exact=True)).to_be_visible()
    expect(types.get_by_role("button", name="Personas", exact=True)).to_be_visible()
    expect(types.get_by_role("button", name="Lore", exact=True)).to_be_visible()
    expect(workspace.get_by_role("combobox", name="Library scope")).to_be_hidden()
    expect(page.locator(".ui-library-home__summary")).to_have_count(0)
    expect(page.locator(".ui-library-home__context")).to_have_count(0)
    actions = workspace.locator(".ui-library-workspace__actions")
    expect(actions.get_by_role("button", name="New story", exact=True)).to_have_count(1)
    expect(actions.get_by_role("button", name="Import story", exact=True)).to_have_count(1)
    expect(workspace.locator(".ui-library__toolbar").get_by_role(
        "button", name="Import story", exact=True
    )).to_have_count(0)
    expect(page.get_by_text("Lorebooks", exact=True)).to_have_count(0)
    assert page.locator(".ui-library__more use").first.get_attribute("href").endswith(
        "#icon-more"
    )

    types.get_by_role("button", name="Characters", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/library/characters"))
    expect(page.get_by_role("heading", name="Library", level=2)).to_be_visible()
    expect(page.get_by_role("heading", name="Characters", level=2)).to_have_count(0)
    expect(types.get_by_role("button", name="Characters", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(page.locator('[data-library-item="character:7"]')).to_be_visible()
    expect(actions.get_by_role("button", name="Create character", exact=True)).to_be_visible()
    expect(actions.get_by_role("button", name="Import character", exact=True)).to_be_visible()

    types.get_by_role("button", name="Personas", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/library/personas"))
    expect(types.get_by_role("button", name="Personas", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(actions.get_by_role("button", name="Create persona", exact=True)).to_be_visible()
    expect(actions.get_by_role("button", name="Import persona", exact=True)).to_be_visible()

    types.get_by_role("button", name="Lore", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/library/lore"))
    expect(types.get_by_role("button", name="Lore", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(page.locator('[data-library-item="lore:12"]')).to_be_visible()
    expect(workspace.locator(".ui-library-workspace__actions")).to_have_count(0)


def test_library_uses_the_canonical_field_control_contract(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)

    controls = page.locator(
        ".ui-library-workspace__filters :is(input, select), "
        ".ui-library__toolbar :is(input, select)"
    )
    assert controls.count() >= 4
    assert controls.evaluate_all(
        "nodes => nodes.every(node => node.classList.contains('ui-field__control'))"
    )
    expect(page.locator(".ui-library-workspace .ui-input")).to_have_count(0)


def test_library_uses_media_rows_without_internal_id_ordinals_and_stages_filters(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)

    expect(page.locator(".ui-library__index")).to_have_count(0)
    row = page.locator('[data-library-item="story:1"]')
    expect(row.locator("[data-media-fallback]")).to_have_text("T")
    filters = page.get_by_role("button", name="Filters", exact=True)
    expect(filters).to_be_visible()
    expect(page.get_by_role("combobox", name="Library scope")).to_be_hidden()
    filters.click()
    expect(page.get_by_role("combobox", name="Library scope")).to_be_visible()
    expect(page.get_by_role("combobox", name="Sort Library")).to_be_visible()


def test_compact_library_reaches_the_first_result_within_240_pixels(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url, width=390)
    top = page.locator("[data-library-ledger] [data-library-item]").first.evaluate(
        "node => node.getBoundingClientRect().top"
    )
    assert top <= 240, top


def test_library_actions_center_compact_icon_and_label_geometry(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)
    new_story = page.get_by_role("button", name="New story", exact=True)
    geometry = new_story.evaluate(
        """node => {
          const style = getComputedStyle(node);
          const icon = node.querySelector('.ui-icon').getBoundingClientRect();
          const label = node.querySelector('span').getBoundingClientRect();
          return {
            display: style.display,
            alignItems: style.alignItems,
            gap: parseFloat(style.gap),
            fontSize: parseFloat(style.fontSize),
            iconCenter: icon.top + icon.height / 2,
            labelCenter: label.top + label.height / 2,
          };
        }"""
    )
    assert geometry["display"] in {"flex", "inline-flex"}, geometry
    assert geometry["alignItems"] == "center", geometry
    assert geometry["gap"] == 6, geometry
    assert geometry["fontSize"] == 14, geometry
    assert abs(geometry["iconCenter"] - geometry["labelCenter"]) <= 1, geometry

    page.get_by_role("button", name="Filters", exact=True).click()
    sort_select = page.get_by_role("combobox", name="Sort Library")
    select_style = sort_select.evaluate(
        """node => {
          const style = getComputedStyle(node);
          return {
            radius: parseFloat(style.borderRadius),
            fontSize: parseFloat(style.fontSize),
            appearance: style.appearance,
          };
        }"""
    )
    assert select_style["radius"] == 9, select_style
    assert select_style["fontSize"] == 14, select_style
    assert select_style["appearance"] == "none", select_style
    assert page.get_by_role("heading", name="Library", level=2).evaluate(
        "node => getComputedStyle(node).outlineStyle"
    ) == "none"


def test_story_import_action_stages_the_existing_import_workflow(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)

    page.evaluate(
        """() => {
          window.__storyImportWorkflow = null;
          document.addEventListener('sonder:library-select', event => {
            window.__storyImportWorkflow = event.detail?.workflow || null;
          }, { once: true });
        }"""
    )

    page.get_by_role("button", name="Import story", exact=True).click()

    expect(page).to_have_url(re.compile(r"#/library/stories\?.*mode=import"))
    root = page.locator("html")
    expect(root).to_have_attribute("data-inspector-open", "true")
    assert page.evaluate("window.__storyImportWorkflow") == "story-import"


def test_compact_library_navigation_controls_meet_touch_minimum(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url, width=390)
    sizes = page.locator(
        ".ui-library-workspace__filters :is(input, select, button):visible, "
        ".ui-library__toolbar :is(input, select, button):visible, .ui-library__more:visible"
    ).evaluate_all("nodes => nodes.map(node => node.getBoundingClientRect().height)")
    assert sizes and min(sizes) >= 44, sizes


def test_story_selection_requires_explicit_open_action(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)

    page.locator('[data-library-item="story:1"]').click()
    expect(page).to_have_url(re.compile(r"#/library(?:/stories)?\?.*item=story%3A1"))
    detail = page.get_by_role("dialog", name="Library details")
    expect(detail.get_by_role("button", name="Open in Play", exact=True)).to_be_visible()
    assert "#/play" not in page.url

    detail.get_by_role("button", name="Open in Play", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/play\?chat=1$"))


def test_story_overflow_is_bare_inside_the_card_and_does_not_select_it(
    page: Page, ui_base_url: str
) -> None:
    _open(page, ui_base_url)

    row = page.locator(".ui-library__row").filter(
        has=page.locator('[data-library-item="story:1"]')
    )
    more = row.get_by_role(
        "button", name="More actions for The Lantern Archive"
    )
    geometry = more.evaluate(
        """node => {
          const row = node.closest('.ui-library__row').getBoundingClientRect();
          const control = node.getBoundingClientRect();
          const style = getComputedStyle(node);
          return {
            contained: control.left >= row.left && control.right <= row.right,
            borderWidth: parseFloat(style.borderWidth),
            background: style.backgroundColor,
          };
        }"""
    )
    assert geometry == {
        "contained": True,
        "borderWidth": 0,
        "background": "rgba(0, 0, 0, 0)",
    }

    initial_url = page.url
    more.click()
    expect(page).to_have_url(initial_url)
    menu = page.get_by_role("menu", name="More actions for The Lantern Archive")
    expect(menu).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Open in Play")).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Edit story")).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Export story")).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Archive story")).to_be_visible()
    expect(page.get_by_role("complementary", name="Library details")).to_be_hidden()

    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(more).to_be_focused()


def test_library_details_pin_expansively_and_close_without_a_gap(
    page: Page, ui_base_url: str
) -> None:
    page.add_init_script(
        """(() => localStorage.setItem('sonder.ui-next', JSON.stringify({
          version: 2,
          appearance: {},
          navigation: {},
          panes: { inspector: { open: true, pinned: true, size: 'rail' } },
          drafts: {},
        })))()"""
    )
    _open(page, ui_base_url)
    page.locator('[data-library-item="story:1"]').click()

    root = page.locator("html")
    inspector = page.get_by_role("complementary", name="Library details")
    expect(root).to_have_attribute("data-inspector-kind", "library-details")
    expect(inspector).to_be_visible()
    expect(root).to_have_attribute("data-context-mode", "pinned")
    assert inspector.evaluate("node => node.getBoundingClientRect().width") >= 320
    action_geometry = inspector.locator(".ui-library-detail__actions").evaluate(
        """node => {
          const panel = node.closest('.ui-shell__inspector').getBoundingClientRect();
          const controls = [...node.children].map(child => child.getBoundingClientRect());
          return {
            scrollFits: node.scrollWidth <= node.clientWidth + 1,
            controlsFit: controls.every(control => control.left >= panel.left - 1
              && control.right <= panel.right + 1),
          };
        }"""
    )
    assert action_geometry == {"scrollFits": True, "controlsFit": True}

    inspector.get_by_role("button", name="Back", exact=True).click()
    expect(inspector).to_be_hidden()
    geometry = page.evaluate(
        """() => {
          const workspace = document.querySelector('[data-ui-region="workspace"]')
            .getBoundingClientRect();
          return {
            workspaceRight: workspace.right,
            viewportRight: document.documentElement.clientWidth,
          };
        }"""
    )
    assert abs(geometry["workspaceRight"] - geometry["viewportRight"]) <= 1


def test_library_runtime_rejects_stale_results_and_bounds_identity_state(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=alpha98-ui15-5b0f039aae29`
          );
          const libraryModule = await import(
            `${base}/static/js/ui-next/library-runtime.js?release=alpha98-ui15-5b0f039aae29`
          );
          const store = storeModule.createStore();
          let current = {
            destination: "library", segments: [], query: {},
            canonicalHash: "#/library",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: current });
          const pending = [];
          const apiClient = {
            get: (path, options) => new Promise((resolve, reject) => {
              pending.push({ path, options, resolve, reject });
            }),
            cancel: () => true,
          };
          let envelope = { version: 2, panes: {}, appearance: {}, navigation: {}, drafts: {} };
          const localState = {
            snapshot: () => structuredClone(envelope),
            setRecord: (name, value) => { envelope = { ...envelope, [name]: structuredClone(value) }; },
          };
          const navigations = [];
          const router = {
            current: () => current,
            navigate: (route, options) => { navigations.push({ route, options }); return route; },
          };
          const runtime = libraryModule.createLibraryRuntime({
            store, apiClient, localState, router,
          });
          current = {
            destination: "library", segments: ["characters"], query: { q: "new" },
            canonicalHash: "#/library/characters?q=new",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: current });
          const payload = name => ({
            items: [{ kind: "character", id: name === "new" ? 2 : 1,
              key: `character:${name === "new" ? 2 : 1}`, name,
              summary: "", associations: [], use_count: 0 }],
            facets: { types: {}, scopes: {} },
            page: { offset: 0, limit: 100, returned: 1, total: 1 },
            query: {},
          });
          store.dispatch({
            type: "server/patch", slice: "library",
            value: { authoring: { owner: "story:1", status: "dirty" } },
          });
          pending[1].resolve({ data: payload("new") });
          await Promise.resolve(); await Promise.resolve();
          pending[0].resolve({ data: payload("old") });
          await Promise.resolve(); await Promise.resolve();
          for (let index = 1; index <= 55; index += 1) {
            runtime.recordRecent(`character:${index}`);
          }
          for (let index = 1; index <= 25; index += 1) {
            runtime.toggleFavorite(`lore:${index}`);
          }
          const normalized = libraryModule.normalizeLibraryRoute({
            segments: ["characters"],
            query: { scope: "story", story: "missing", item: "Mara Venn", sort: "newest" },
          });
          runtime.teardown();
          return {
            item: store.getSnapshot().library.items[0].name,
            authoring: store.getSnapshot().library.authoring,
            requests: pending.map(entry => ({ path: entry.path, owner: entry.options.owner,
              hasOwnerCheck: typeof entry.options.isCurrent === "function" })),
            recents: envelope.panes.library.recents.length,
            favorites: envelope.panes.library.favorites.length,
            normalized: {
              scope: normalized.scope, item: normalized.item, sort: normalized.sort,
              invalid: normalized.invalid, query: normalized.query,
            },
            navigations,
          };
        }""",
        ui_base_url,
    )
    assert result["item"] == "new"
    assert result["authoring"] == {"owner": "story:1", "status": "dirty"}
    assert result["recents"] == 50
    assert result["favorites"] == 20
    assert all(request["hasOwnerCheck"] for request in result["requests"])
    assert result["requests"][0]["owner"] == "#/library"
    assert result["requests"][1]["owner"] == "#/library/characters?q=new"
    assert result["normalized"] == {
        "scope": "all", "item": "", "sort": "name", "invalid": True,
        "query": {},
    }


def test_lore_can_prepare_a_lived_location_for_the_current_story(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=alpha98-ui15-5b0f039aae29`
          );
          const libraryModule = await import(
            `${base}/static/js/ui-next/library-runtime.js?release=alpha98-ui15-5b0f039aae29`
          );
          const route = {
            destination: "library", segments: ["lore"],
            query: { item: "lore:12" },
            canonicalHash: "#/library/lore?item=lore%3A12",
          };
          const store = storeModule.createStore({
            route,
            story: { status: "ready", data: { chat: { id: 5 } }, frameId: null },
          });
          const item = {
            kind: "lore", id: 12, key: "lore:12", name: "Quiet Roads",
            summary: "Paths between old signal towers.", reusable: true,
            archived: false, use_count: 0, associations: [],
          };
          const projection = {
            items: [item], facets: { types: {}, scopes: {} },
            page: { offset: 0, limit: 100, returned: 1, total: 1 }, query: {},
          };
          const posts = [];
          const apiClient = {
            get: async () => ({ data: structuredClone(projection) }),
            post: async (path, body, options) => {
              posts.push({ path, body, current: options.isCurrent() });
              if (path.endsWith("/lorebooks")) return { data: { lorebook_id: 212 } };
              return { data: { charters: { items: { archive: {} } } } };
            },
            cancel: () => true,
          };
          let envelope = { version: 2, panes: {}, appearance: {}, navigation: {}, drafts: {} };
          const localState = {
            snapshot: () => structuredClone(envelope),
            setRecord: (name, value) => { envelope = { ...envelope, [name]: structuredClone(value) }; },
          };
          const router = { current: () => route, navigate: () => true };
          const runtime = libraryModule.createLibraryRuntime({ store, apiClient, localState, router });
          await Promise.resolve(); await Promise.resolve();
          const generated = await runtime.generateLocationFromLore(item, {
            enabled: true, brief: "A signal keep", horizonHours: 168,
            characterHistories: [],
          });
          const mutation = store.getSnapshot().library.mutation;
          runtime.teardown();
          return { posts, generated, mutation };
        }""",
        ui_base_url,
    )
    assert result["posts"] == [
        {
            "path": "/api/chats/5/lorebooks",
            "body": {"lorebook_id": 12},
            "current": True,
        },
        {
            "path": "/api/chats/5/charters/generate",
            "body": {
                "enabled": True,
                "brief": "A signal keep",
                "horizon_hours": 168,
                "active_tail_hours": 96,
                "generate_history": True,
                "lorebook_id": 12,
                "owning_lorebook_id": 212,
            },
            "current": True,
        },
    ]
    assert result["generated"] == {"charters": {"items": {"archive": {}}}}
    assert result["mutation"]["message"] == "1 institutions prepared."


def test_library_mutations_keep_story_owner_and_undo_expires(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=alpha98-ui15-5b0f039aae29`
          );
          const libraryModule = await import(
            `${base}/static/js/ui-next/library-runtime.js?release=alpha98-ui15-5b0f039aae29`
          );
          const item = {
            kind: "character", id: 7, key: "character:7", name: "Mara Venn",
            summary: "", reusable: true, archived: false, use_count: 1,
            associations: [{ story_id: 1, story_name: "Story A", state: "active" }],
          };
          const payload = {
            items: [item], facets: { types: {}, scopes: {} },
            page: { offset: 0, limit: 100, returned: 1, total: 1 }, query: {},
          };
          const store = storeModule.createStore();
          let current = {
            destination: "library", segments: ["characters"],
            query: { story: "1", item: "character:7" },
            canonicalHash: "#/library/characters?item=character%3A7&story=1",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: current });
          const pending = [];
          const apiClient = {
            get: async () => ({ data: structuredClone(payload) }),
            request: (method, path, options) => new Promise((resolve, reject) => {
              pending.push({ method, path, options, resolve, reject });
            }),
            cancel: () => true,
          };
          let envelope = { version: 2, panes: {}, appearance: {}, navigation: {}, drafts: {} };
          const localState = {
            snapshot: () => structuredClone(envelope),
            setRecord: (name, value) => { envelope = { ...envelope, [name]: structuredClone(value) }; },
          };
          const router = { current: () => current, navigate: () => true };
          const runtime = libraryModule.createLibraryRuntime({ store, apiClient, localState, router });
          await Promise.resolve(); await Promise.resolve();

          const late = runtime.setAssociation(item, item.associations[0]);
          current = {
            ...current, query: { story: "2", item: "character:7" },
            canonicalHash: "#/library/characters?item=character%3A7&story=2",
          };
          const first = pending[0];
          if (first.options.isCurrent({ owner: first.options.owner })) {
            first.resolve({ data: { ok: true } });
          } else {
            first.reject({ kind: "stale" });
          }
          const lateAccepted = await late;

          current = {
            ...current, query: { story: "1", item: "character:7" },
            canonicalHash: "#/library/characters?item=character%3A7&story=1",
          };
          const accepted = runtime.setAssociation(
            { ...item, associations: [{ ...item.associations[0], state: "dormant" }] },
            { ...item.associations[0], state: "dormant" },
          );
          const second = pending[1];
          if (second.options.isCurrent({ owner: second.options.owner })) {
            second.resolve({ data: { ok: true } });
          } else {
            second.reject({ kind: "stale" });
          }
          const acceptedNow = await accepted;
          const receipt = store.getSnapshot().library.undo;
          const originalNow = Date.now;
          Date.now = () => receipt.expiresAt + 1;
          const expiredUndoAccepted = await runtime.runUndo();
          Date.now = originalNow;
          const finalUndo = store.getSnapshot().library.undo;
          runtime.teardown();
          return {
            lateAccepted, acceptedNow, expiredUndoAccepted,
            firstOwner: first.options.owner,
            secondOwner: second.options.owner,
            hasFirstGuard: typeof first.options.isCurrent === "function",
            finalUndo,
            requestCount: pending.length,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "lateAccepted": False,
        "acceptedNow": True,
        "expiredUndoAccepted": False,
        "firstOwner": "character:7:1:cast-remove",
        "secondOwner": "character:7:1:cast-reactivate",
        "hasFirstGuard": True,
        "finalUndo": None,
        "requestCount": 2,
    }


def test_library_search_route_and_desktop_detail_are_truthful(
    page: Page, ui_base_url: str,
) -> None:
    _open(page, ui_base_url)
    page.get_by_role("button", name="Characters", exact=True).click()
    expect(page.locator("[data-library-ledger] [data-library-item]")).to_have_count(1)
    page.locator('[data-library-item="character:7"]').click()

    expect(page).to_have_url(re.compile(r"item=character%3A7"))
    detail = page.get_by_role("dialog", name="Library details")
    expect(detail.get_by_role("heading", name="Mara Venn")).to_be_visible()
    expect(detail.get_by_text("The Lantern Archive")).to_be_visible()
    expect(detail.get_by_text("Active", exact=True)).to_be_visible()
    detail.get_by_role("button", name="Back", exact=True).click()

    search = page.get_by_role("searchbox", name="Search Library")
    search.fill("Quiet Road")
    search.press("Enter")
    expect(page).to_have_url(re.compile(r"q=Quiet\+Road"))


def test_compact_library_detail_is_history_staged_and_targets_are_large(
    page: Page, ui_base_url: str,
) -> None:
    _open(page, ui_base_url, width=390)
    page.get_by_role("button", name="Filters", exact=True).click()
    expect(page.get_by_role("combobox", name="Library scope")).to_be_visible()
    page.get_by_role("button", name="Lore", exact=True).click()
    page.locator('[data-library-item="lore:12"]').click()

    sheet = page.get_by_role("dialog", name="Library details")
    expect(sheet).to_be_visible()
    expect(sheet.get_by_role("heading", name="Quiet Roads")).to_be_visible()
    sizes = page.locator("[data-library-item]").evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect().height)"
    )
    assert min(sizes) >= 44

    page.go_back()
    expect(sheet).to_be_hidden()
    expect(page.locator("[data-library-ledger]")).to_be_visible()


def test_compact_library_deep_link_stages_detail_then_back_restores_context(
    page: Page, ui_base_url: str,
) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route(
        "**/api/library?*",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(_projection())),
    )
    page.goto(f"{ui_base_url}/static/ui-next.html#/library/lore?item=lore%3A12")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")

    sheet = page.get_by_role("dialog", name="Library details")
    expect(sheet).to_be_visible()
    expect(sheet.get_by_role("heading", name="Quiet Roads")).to_be_visible()
    page.go_back()
    expect(sheet).to_be_hidden()
    expect(page.locator("[data-library-ledger]")).to_be_visible()


def test_japanese_localizes_late_library_detail_without_translating_story_data(
    page: Page, ui_base_url: str,
) -> None:
    catalog = json.loads(
        (Path(__file__).parents[1] / "language_packs" / "ja" / "ui.json")
        .read_text(encoding="utf-8")
    )
    boot = {**BOOTSTRAP, "ui_language": "ja", "ui_messages": catalog}
    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(
            content_type="application/json", body=json.dumps(boot, ensure_ascii=False),
        ),
    )
    page.route(
        "**/api/library?*",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(_projection())),
    )
    page.goto(f"{ui_base_url}/static/ui-next.html#/library/characters?item=character%3A7")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")

    detail = page.get_by_role("dialog", name="ライブラリの詳細")
    expect(detail.get_by_role("heading", name="Mara Venn")).to_be_visible()
    expect(detail.get_by_text("ストーリーでの使用", exact=True)).to_be_visible()
    expect(detail.get_by_role("button", name="アクティブキャストから外す")).to_be_visible()
    expect(detail.get_by_text("The Lantern Archive", exact=True)).to_be_visible()


def test_library_character_lifecycle_and_bounded_undo_use_server_truth(
    page: Page, ui_base_url: str,
) -> None:
    state = {"active": True, "archived": False}

    def projection():
        associations = [{
            "story_id": 1, "story_name": "The Lantern Archive",
            "state": "active" if state["active"] else "dormant",
        }]
        return _projection([
            ITEMS[0],
            {**ITEMS[1], "archived": state["archived"], "associations": associations},
        ])

    def library_route(route):
        archived_view = "visibility=archived" in route.request.url
        payload = projection()
        payload["items"] = [
            item for item in payload["items"]
            if bool(item.get("archived")) == archived_view
        ]
        payload["page"] = {
            "offset": 0, "limit": 100,
            "returned": len(payload["items"]), "total": len(payload["items"]),
        }
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    def character_route(route):
        if route.request.method == "DELETE":
            state["active"] = False
        elif route.request.method == "POST":
            state["active"] = True
        route.fulfill(content_type="application/json", body='{"ok":true}')

    def archive_route(route):
        state["archived"] = route.request.method == "PUT"
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"key": "character:7", "archived": state["archived"], "changed": True}),
        )

    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route("**/api/library?*", library_route)
    page.route("**/api/chats/1/characters**", character_route)
    page.route("**/api/library/character/7/archive", archive_route)
    page.goto(f"{ui_base_url}/static/ui-next.html#/library/characters")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    page.locator('[data-library-item="character:7"]').click()
    detail = page.get_by_role("dialog", name="Library details")

    detail.get_by_role("button", name="Remove from active cast").click()
    expect(detail.get_by_text("Dormant", exact=True)).to_be_visible()
    expect(detail.get_by_role("button", name="Undo")).to_be_visible()
    detail.get_by_role("button", name="Undo").click()
    expect(detail.get_by_text("Active", exact=True)).to_be_visible()

    detail.get_by_text("More", exact=True).click()
    detail.get_by_role("button", name="Archive character").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    expect(page.locator('[data-library-item="character:7"]')).to_have_count(0)
    page.get_by_role("button", name="Undo").click()
    expect(page.locator('[data-library-item="character:7"]')).to_be_visible()


def test_row_menu_archive_refreshes_library_and_play_story_choices_immediately(
    page: Page, ui_base_url: str,
) -> None:
    state = {"archived": False}

    def library_route(route) -> None:
        active = [] if state["archived"] else [ITEMS[0]]
        payload = _projection(active)
        payload["stories"] = [] if state["archived"] else BOOTSTRAP["chats"]
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    def archive_route(route) -> None:
        state["archived"] = route.request.method == "PUT"
        route.fulfill(
            content_type="application/json",
            body=json.dumps({"key": "story:1", "archived": state["archived"], "changed": True}),
        )

    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route("**/api/library?*", library_route)
    page.route("**/api/library/story/1/archive", archive_route)
    page.goto(f"{ui_base_url}/static/ui-next.html#/library/stories")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")

    page.get_by_role("button", name="More actions for The Lantern Archive").click()
    page.get_by_role("menuitem", name="Archive story").click()
    expect(page.locator('[data-library-item="story:1"]')).to_have_count(0)

    page.get_by_role("link", name="Play", exact=True).click()
    expect(page.get_by_role("button", name="The Lantern Archive")).to_have_count(0)


def test_primary_persona_is_protected_and_story_delete_names_its_scope(
    page: Page, ui_base_url: str,
) -> None:
    deleted = {"story": False}
    persona = {
        "kind": "persona", "id": 9, "key": "persona:9", "name": "Ilyra",
        "summary": "The player persona.", "subtype": "persona", "created": None,
        "reusable": True, "archived": False, "use_count": 1,
        "associations": [{
            "story_id": 1, "story_name": "The Lantern Archive", "state": "primary",
        }],
    }
    boot = {**BOOTSTRAP, "personas": [{"id": 9, "name": "Ilyra"}]}

    def library_route(route):
        items = [persona] if deleted["story"] else [ITEMS[0], persona]
        route.fulfill(content_type="application/json", body=json.dumps(_projection(items)))

    def delete_story(route):
        deleted["story"] = True
        route.fulfill(content_type="application/json", body='{"ok":true}')

    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(boot)),
    )
    page.route("**/api/library?*", library_route)
    page.route("**/api/chats/1", delete_story)
    page.goto(f"{ui_base_url}/static/ui-next.html#/library/personas")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")

    page.locator('[data-library-item="persona:9"]').click()
    detail = page.get_by_role("dialog", name="Library details")
    expect(detail.get_by_text("Primary", exact=True)).to_be_visible()
    expect(detail.get_by_text("Primary persona · change in Story setup")).to_be_visible()
    expect(detail.get_by_role("button", name=re.compile("Remove"))).to_have_count(0)

    detail.get_by_role("button", name="Back", exact=True).click()
    page.get_by_role("button", name="Stories", exact=True).click()
    page.locator('[data-library-item="story:1"]').click()
    detail.get_by_role("button", name="Delete story…").click()
    expect(detail.get_by_text(re.compile("complete story, its history, and story-owned lore"))).to_be_visible()
    detail.get_by_role("button", name="Delete this story").click()
    expect(page.locator('[data-library-item="story:1"]')).to_have_count(0)
    page.get_by_role("button", name="Personas", exact=True).click()
    expect(page.locator('[data-library-item="persona:9"]')).to_be_visible()


def test_lore_detach_targets_story_copy_and_undo_reattaches_origin(
    page: Page, ui_base_url: str,
) -> None:
    attached = {"value": True}
    requests = []
    lore = {
        **ITEMS[2], "use_count": 1,
        "associations": [{
            "story_id": 1, "story_name": "The Lantern Archive",
            "state": "attached", "story_item_id": 212,
        }],
    }

    def library_route(route):
        item = lore if attached["value"] else {**lore, "use_count": 0, "associations": []}
        route.fulfill(content_type="application/json", body=json.dumps(_projection([ITEMS[0], item])))

    def association_route(route):
        requests.append({
            "method": route.request.method,
            "url": route.request.url,
            "body": route.request.post_data_json if route.request.post_data else None,
        })
        attached["value"] = route.request.method == "POST"
        result = {"lorebook_id": 212} if attached["value"] else {"ok": True}
        route.fulfill(content_type="application/json", body=json.dumps(result))

    page.route(
        "**/api/bootstrap",
        lambda route: route.fulfill(content_type="application/json", body=json.dumps(BOOTSTRAP)),
    )
    page.route("**/api/library?*", library_route)
    page.route("**/api/chats/1/lorebooks**", association_route)
    page.goto(f"{ui_base_url}/static/ui-next.html#/library/lore")
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    page.locator('[data-library-item="lore:12"]').click()
    detail = page.get_by_role("dialog", name="Library details")

    detail.get_by_role("button", name="Detach from story").click()
    expect(detail.get_by_text("Not used by a story.")).to_be_visible()
    detail.get_by_role("button", name="Undo").click()
    expect(detail.get_by_text("Attached", exact=True)).to_be_visible()

    assert requests[0]["method"] == "DELETE"
    assert requests[0]["url"].endswith("/api/chats/1/lorebooks/212")
    assert requests[1]["method"] == "POST"
    assert requests[1]["url"].endswith("/api/chats/1/lorebooks")
    assert requests[1]["body"] == {"lorebook_id": 12}
