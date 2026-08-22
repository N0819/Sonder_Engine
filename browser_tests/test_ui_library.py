"""Real-browser contracts for the replacement WP-06 Library."""

from __future__ import annotations

import json
import re

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


def _open(page: Page, ui_base_url: str, *, width: int = 1280) -> None:
    page.set_viewport_size({"width": width, "height": 800 if width > 700 else 844})
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
    expect(page.get_by_role("heading", name="Library", level=1)).to_be_visible()
    expect(page.locator("[data-library-ledger] [data-library-item]")).to_have_count(3)


def test_library_runtime_rejects_stale_results_and_bounds_identity_state(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=wp06.1`
          );
          const libraryModule = await import(
            `${base}/static/js/ui-next/library-runtime.js?release=wp06.1`
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
    assert result["recents"] == 50
    assert result["favorites"] == 20
    assert all(request["hasOwnerCheck"] for request in result["requests"])
    assert result["requests"][0]["owner"] == "#/library"
    assert result["requests"][1]["owner"] == "#/library/characters?q=new"
    assert result["normalized"] == {
        "scope": "all", "item": "", "sort": "name", "invalid": True,
        "query": {},
    }


def test_library_search_route_and_desktop_detail_are_truthful(
    page: Page, ui_base_url: str,
) -> None:
    _open(page, ui_base_url)
    page.get_by_role("button", name=re.compile("Mara Venn")).click()

    expect(page).to_have_url(re.compile(r"item=character%3A7"))
    detail = page.get_by_role("complementary", name="Library details")
    expect(detail.get_by_role("heading", name="Mara Venn")).to_be_visible()
    expect(detail.get_by_text("The Lantern Archive")).to_be_visible()
    expect(detail.get_by_text("Active", exact=True)).to_be_visible()

    search = page.get_by_role("searchbox", name="Search Library")
    search.fill("Quiet Road")
    search.press("Enter")
    expect(page).to_have_url(re.compile(r"q=Quiet\+Road"))


def test_compact_library_detail_is_history_staged_and_targets_are_large(
    page: Page, ui_base_url: str,
) -> None:
    _open(page, ui_base_url, width=390)
    expect(page.get_by_role("button", name="Not used", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Multiple stories", exact=True)).to_be_visible()
    page.get_by_role("button", name=re.compile("Quiet Roads")).click()

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
