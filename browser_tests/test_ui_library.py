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
    visibility = page.get_by_role("combobox", name="Library visibility")
    expect(visibility).to_have_value("active")
    expect(visibility).to_be_visible()
    assert page.locator(".ui-library__content").evaluate(
        "node => node.scrollWidth - node.clientWidth"
    ) == 0


def test_library_runtime_rejects_stale_results_and_bounds_identity_state(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=wp07.1`
          );
          const libraryModule = await import(
            `${base}/static/js/ui-next/library-runtime.js?release=wp07.1`
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


def test_library_mutations_keep_story_owner_and_undo_expires(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=wp07.1`
          );
          const libraryModule = await import(
            `${base}/static/js/ui-next/library-runtime.js?release=wp07.1`
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

    detail = page.get_by_role("complementary", name="ライブラリの詳細")
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
    page.get_by_role("button", name=re.compile("Mara Venn")).click()
    detail = page.get_by_role("complementary", name="Library details")

    detail.get_by_role("button", name="Remove from active cast").click()
    expect(detail.get_by_text("Dormant", exact=True)).to_be_visible()
    expect(detail.get_by_role("button", name="Undo")).to_be_visible()
    detail.get_by_role("button", name="Undo").click()
    expect(detail.get_by_text("Active", exact=True)).to_be_visible()

    detail.get_by_role("button", name="Archive character").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("Mara Venn"))).to_have_count(0)
    page.get_by_role("button", name="Undo").click()
    expect(page.get_by_role("button", name=re.compile("Mara Venn"))).to_be_visible()


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

    page.get_by_role("button", name=re.compile("Ilyra")).click()
    detail = page.get_by_role("complementary", name="Library details")
    expect(detail.get_by_text("Primary", exact=True)).to_be_visible()
    expect(detail.get_by_text("Primary persona · change in Story setup")).to_be_visible()
    expect(detail.get_by_role("button", name=re.compile("Remove"))).to_have_count(0)

    page.locator('[data-library-item="story:1"]').click()
    detail.get_by_role("button", name="Delete story…").click()
    expect(detail.get_by_text(re.compile("complete story, its history, and story-owned lore"))).to_be_visible()
    detail.get_by_role("button", name="Delete this story").click()
    expect(page.locator('[data-library-item="story:1"]')).to_have_count(0)
    expect(page.get_by_role("button", name=re.compile("Ilyra"))).to_be_visible()


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
    page.get_by_role("button", name=re.compile("Quiet Roads")).click()
    detail = page.get_by_role("complementary", name="Library details")

    detail.get_by_role("button", name="Detach from story").click()
    expect(detail.get_by_text("Not used by a story.")).to_be_visible()
    detail.get_by_role("button", name="Undo").click()
    expect(detail.get_by_text("Attached", exact=True)).to_be_visible()

    assert requests[0]["method"] == "DELETE"
    assert requests[0]["url"].endswith("/api/chats/1/lorebooks/212")
    assert requests[1]["method"] == "POST"
    assert requests[1]["url"].endswith("/api/chats/1/lorebooks")
    assert requests[1]["body"] == {"lorebook_id": 12}
