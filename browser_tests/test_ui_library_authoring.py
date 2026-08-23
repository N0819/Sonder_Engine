"""Real-browser contracts for Library authoring ownership and recovery."""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page
from playwright.sync_api import expect


BOOTSTRAP = {
    "ui_language": "en", "ui_direction": "ltr", "ui_messages": {},
    "chats": [{"id": 1, "name": "Lantern Archive"}],
    "characters": [],
    "personas": [{"id": 9, "name": "Mira"}],
    "lorebooks": [], "providers": [], "language_packs": [],
    "extensions": [], "extension_errors": [], "extension_lanes": [],
}

PERSON_DOCUMENT = {
    "identity": {
        "uid": "char_mara",
        "name": "Mara Venn",
        "aliases": ["Mara"],
        "pronouns": {"subject": "she", "object": "her", "possessive": "her"},
    },
    "initial_outfit": {"wearing": [], "state": [], "regions": {}},
    "simulation": {
        "tier": "mid", "temperature": 0.8, "sampler": {},
        "curiosity": 0.5, "offscreen_agent": False,
    },
    "embodiment": {
        "senses": [],
        "visible": {"summary": "A rain-dark courier."},
        "scent": "rain", "latent": [], "extra_parts": [],
    },
    "psychology": {"traits": [], "values": []},
    "social": {"voice": {"register": "quiet"}},
    "competence": {"abilities": []},
    "knowledge": {"public_history": "A courier.", "private_history": []},
    "initial_state": {"mood": {"label": "watchful"}},
    "opening": {"first_message": "The rain followed you in.", "greetings": []},
    "extension_payload": {"note": "must survive"},
}


def _route_character_editor(page: Page) -> None:
    def projection(route):
        route.fulfill(content_type="application/json", body=json.dumps({
            "items": [{
                "kind": "character", "id": 7, "key": "character:7",
                "name": "Mara Venn", "summary": "A rain-dark courier.",
                "subtype": "character", "created": 1, "reusable": True,
                "archived": False, "use_count": 0, "associations": [],
            }],
            "facets": {
                "types": {"story": 0, "character": 1, "persona": 0, "lore": 0},
                "scopes": {"all": 1, "story": 0, "unassigned": 1, "multiple": 0},
            },
            "page": {"offset": 0, "limit": 100, "returned": 1, "total": 1},
            "query": {"scope": "all", "sort": "name", "visibility": "active"},
        }))

    page.route("**/api/bootstrap", lambda route: route.fulfill(
        content_type="application/json",
        body=json.dumps({**BOOTSTRAP, "characters": [{"id": 7, "name": "Mara Venn"}]}),
    ))
    page.route("**/api/library?*", projection)
    page.route("**/api/library/authoring/character/7", lambda route: route.fulfill(
        content_type="application/json",
        body=json.dumps({
            "kind": "character", "id": 7, "owner": "character:7",
            "revision": "revision-one", "document": PERSON_DOCUMENT,
        }),
    ))


def test_people_authoring_owns_the_library_destination_workspace(
    page: Page, ui_base_url: str,
) -> None:
    """Removing the workspace route would put the long form back in Inspector."""

    _route_character_editor(page)
    response = page.goto(
        f"{ui_base_url}/static/ui-next.html"
        "#/library/characters?item=character%3A7&mode=edit"
    )
    assert response is not None and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")

    expect(page.locator("[data-person-workspace]")).to_be_visible()
    expect(page.locator(".ui-library")).to_have_count(0)
    expect(page.get_by_role("complementary", name="Library details")).to_be_hidden()
    assert page.locator("html").get_attribute("data-library-authoring") == "true"


def test_character_quick_start_sends_alpha98_history_contract(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui2-3f44d1cc71ed`);
          const runtimeModule = await import(`${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui2-3f44d1cc71ed`);
          const store = storeModule.createStore();
          const route = { destination: 'library', segments: ['characters'], query: { item: 'character:7', mode: 'edit' }, canonicalHash: '#/library/characters?item=character%3A7&mode=edit' };
          store.dispatch({ type: 'presentation/replace', slice: 'route', value: route });
          const loads = [];
          const writes = [];
          const navigations = [];
          const apiClient = {
            get: (path, options) => new Promise(resolve => loads.push({ path, options, resolve })),
            request: (method, path, options) => new Promise(resolve => writes.push({ method, path, options, resolve })),
            cancel: () => true,
          };
          const runtime = runtimeModule.createLibraryAuthoringRuntime({
            store, apiClient,
            localState: { getDraft: () => null, setDraft() {}, clearDraft() {} },
            router: { current: () => route, navigate: value => navigations.push(value) },
            target: { addEventListener() {}, removeEventListener() {} },
          });
          loads[0].resolve({ data: { kind: 'character', id: 7, owner: 'character:7', revision: 'r1', document: { identity: { name: 'Ilya' }, opening: { greetings: [{ prose: 'Hello' }] } } } });
          await Promise.resolve(); await Promise.resolve();
          const pending = runtime.quickStart({
            personaId: 3, greetingIndex: 0, lorebookId: 12, alreadyKnown: false, language: 'en',
            livedLocation: { enabled: true, brief: 'A hospital built into a cliff', horizon_hours: 168, active_tail_hours: 96, generate_history: true, character_history: { mode: 'resident', brief: 'Night-shift surgeon' } },
          });
          await Promise.resolve();
          const write = writes[0];
          write.resolve({ data: { chat_id: 44 } });
          const accepted = await pending;
          runtime.teardown();
          return { accepted, method: write.method, path: write.path, body: write.options.body, navigations };
        }""",
        ui_base_url,
    )
    assert result["accepted"] is True
    assert result["method"] == "POST"
    assert result["path"] == "/api/characters/7/start"
    assert result["body"] == {
        "persona_id": 3, "greeting_index": 0, "lorebook_id": 12,
        "already_known": False, "language": "en",
        "lived_location": {
            "enabled": True, "brief": "A hospital built into a cliff",
            "horizon_hours": 168, "active_tail_hours": 96,
            "generate_history": True,
            "character_history": {"mode": "resident", "brief": "Night-shift surgeon"},
        },
    }


def test_story_editor_is_routed_and_round_trips_a_recovered_draft(
    page: Page, ui_base_url: str,
) -> None:
    stored = {
        "name": "Lantern Archive", "scenario": "Rain", "persona_id": None,
    }
    authoring_calls = []

    def projection(route):
        route.fulfill(content_type="application/json", body=json.dumps({
            "items": [{
                "kind": "story", "id": 1, "key": "story:1",
                "name": stored["name"], "summary": stored["scenario"],
                "subtype": "", "created": 1, "reusable": False,
                "archived": False, "use_count": 0, "associations": [],
            }],
            "facets": {
                "types": {"story": 1, "character": 0, "persona": 0, "lore": 0},
                "scopes": {"all": 1, "story": 0, "unassigned": 0, "multiple": 0},
            },
            "page": {"offset": 0, "limit": 100, "returned": 1, "total": 1},
            "query": {"scope": "all", "sort": "name", "visibility": "active"},
        }))

    def authoring(route):
        nonlocal stored
        authoring_calls.append(route.request.method)
        if route.request.method == "PUT":
            body = route.request.post_data_json
            assert body["expected_revision"] == "revision-one"
            stored = {
                "name": body["name"], "scenario": body["scenario"],
                "persona_id": body["persona_id"],
            }
            payload = {
                "kind": "story", "id": 1, "owner": "story:1",
                "revision": "revision-two", "document": stored,
            }
        else:
            payload = {
                "kind": "story", "id": 1, "owner": "story:1",
                "revision": "revision-one", "document": stored,
                "overview": {
                    "cast": [], "personas": [], "lore": [],
                    "activity": {"turn_count": 4, "recent": []}, "issues": [],
                },
            }
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    page.set_viewport_size({"width": 1280, "height": 800})
    page.route("**/api/bootstrap", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps(BOOTSTRAP),
    ))
    page.route("**/api/library?*", projection)
    page.route("**/api/library/authoring/story/1", authoring)
    page.route("**/api/chats/1", authoring)
    response = page.goto(
        f"{ui_base_url}/static/ui-next.html#/library/stories?item=story%3A1"
    )
    assert response is not None and response.ok
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    inspector = page.locator("[data-shell-inspector]:visible")
    expect(inspector.get_by_role("button", name="Edit story")).to_be_visible()
    expect(inspector.get_by_text("4 turns recorded")).to_be_visible()

    inspector.get_by_role("button", name="Edit story").click()
    expect(page).to_have_url(re.compile(r"mode=edit"))
    page.wait_for_timeout(100)
    assert authoring_calls.count("GET") >= 2, authoring_calls
    name = inspector.get_by_role("textbox", name="Story name")
    expect(name).to_have_value("Lantern Archive")
    name.fill("Recovered Lantern")
    inspector.get_by_role("textbox", name="Story premise").fill("Rain and brass")
    inspector.get_by_role("combobox", name="Player persona").select_option("9")
    expect(inspector.get_by_text("Unsaved draft")).to_be_visible()

    page.reload()
    page.wait_for_function("document.documentElement.dataset.uiNextState === 'ready'")
    inspector = page.locator("[data-shell-inspector]:visible")
    expect(inspector.get_by_role("textbox", name="Story name")).to_have_value("Recovered Lantern")
    expect(inspector.get_by_text("Recovered local draft")).to_be_visible()
    inspector.get_by_role("button", name="Save story").click()
    expect(inspector.get_by_text("Saved", exact=True)).to_be_visible()
    assert stored == {
        "name": "Recovered Lantern", "scenario": "Rain and brass", "persona_id": 9,
    }


def test_authoring_runtime_preserves_drafts_and_rejects_late_save(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=alpha98-ui2-3f44d1cc71ed`
          );
          const authoringModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui2-3f44d1cc71ed`
          );
          const store = storeModule.createStore();
          let route = {
            destination: "library", segments: ["stories"],
            query: { item: "story:1", mode: "edit" },
            canonicalHash: "#/library/stories?item=story%3A1&mode=edit",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          const loads = [];
          const writes = [];
          const apiClient = {
            get: (path, options) => new Promise((resolve, reject) => {
              loads.push({ path, options, resolve, reject });
            }),
            request: (method, path, options) => new Promise((resolve, reject) => {
              writes.push({ method, path, options, resolve, reject });
            }),
            cancel: () => true,
          };
          const drafts = new Map();
          const localState = {
            getDraft: (type, owner) => drafts.get(`${type}:${owner}`) ?? null,
            setDraft: (type, owner, value) => drafts.set(`${type}:${owner}`, value),
            clearDraft: (type, owner) => drafts.delete(`${type}:${owner}`),
          };
          const listeners = new Map();
          const target = {
            addEventListener: (name, listener) => listeners.set(name, listener),
            removeEventListener: name => listeners.delete(name),
          };
          const router = { current: () => route };
          const runtime = authoringModule.createLibraryAuthoringRuntime({
            store, apiClient, localState, router, target,
          });
          loads[0].resolve({ data: {
            kind: "story", id: 1, owner: "story:1", revision: "rev-one",
            document: { name: "Old", scenario: "Rain", persona_id: null },
            overview: { cast: [], personas: [], lore: [], activity: { turn_count: 0, recent: [] }, issues: [] },
          }});
          await Promise.resolve(); await Promise.resolve();
          runtime.stage({ name: "Draft", scenario: "Rain", persona_id: null });
          const staged = structuredClone(store.getSnapshot().library.authoring);
          const unload = { preventDefault() { this.prevented = true; }, returnValue: undefined };
          listeners.get("beforeunload")(unload);

          const lateSave = runtime.save();
          route = {
            destination: "library", segments: ["stories"],
            query: { item: "story:2", mode: "edit" },
            canonicalHash: "#/library/stories?item=story%3A2&mode=edit",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          writes[0].resolve({ data: {
            kind: "story", id: 1, owner: "story:1", revision: "rev-saved",
            document: { name: "Draft", scenario: "Rain", persona_id: null },
          }});
          const lateAccepted = await lateSave;
          loads[1].resolve({ data: {
            kind: "story", id: 2, owner: "story:2", revision: "rev-two",
            document: { name: "Second", scenario: "Snow", persona_id: null },
            overview: { cast: [], personas: [], lore: [], activity: { turn_count: 0, recent: [] }, issues: [] },
          }});
          await Promise.resolve(); await Promise.resolve();
          const final = structuredClone(store.getSnapshot().library.authoring);
          runtime.teardown();
          return {
            loadPath: loads[0].path,
            loadOwned: loads[0].options.isCurrent({ owner: loads[0].options.owner }),
            save: { method: writes[0].method, path: writes[0].path,
              body: writes[0].options.body },
            staged: { owner: staged.owner, status: staged.status, draft: staged.draft },
            unloadPrevented: unload.prevented === true && unload.returnValue === "",
            lateAccepted,
            firstDraft: drafts.get("library-authoring:story:1"),
            final: { owner: final.owner, status: final.status, document: final.document },
          };
        }""",
        ui_base_url,
    )
    assert result["loadPath"] == "/api/library/authoring/story/1"
    assert result["loadOwned"] is False  # route now belongs to story 2
    assert result["save"] == {
        "method": "PUT",
        "path": "/api/chats/1",
        "body": {
            "name": "Draft",
            "scenario": "Rain",
            "persona_id": None,
            "expected_revision": "rev-one",
        },
    }
    assert result["staged"] == {
        "owner": "story:1",
        "status": "dirty",
        "draft": {"name": "Draft", "scenario": "Rain", "persona_id": None},
    }
    assert result["unloadPrevented"] is True
    assert result["lateAccepted"] is False
    assert result["firstDraft"] is not None
    assert result["final"] == {
        "owner": "story:2",
        "status": "saved",
        "document": {"name": "Second", "scenario": "Snow", "persona_id": None},
    }


def test_authoring_runtime_restores_draft_and_preserves_failed_save(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=alpha98-ui2-3f44d1cc71ed`
          );
          const authoringModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui2-3f44d1cc71ed`
          );
          const store = storeModule.createStore();
          const route = {
            destination: "library", segments: ["stories"],
            query: { item: "story:4", mode: "edit" },
            canonicalHash: "#/library/stories?item=story%3A4&mode=edit",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          const recovered = { name: "Recovered", scenario: "Long draft", persona_id: 9 };
          const drafts = new Map([["library-authoring:story:4", JSON.stringify(recovered)]]);
          const localState = {
            getDraft: (type, owner) => drafts.get(`${type}:${owner}`) ?? null,
            setDraft: (type, owner, value) => drafts.set(`${type}:${owner}`, value),
            clearDraft: (type, owner) => drafts.delete(`${type}:${owner}`),
          };
          const apiClient = {
            get: async () => ({ data: {
              kind: "story", id: 4, owner: "story:4", revision: "rev-four",
              document: { name: "Stored", scenario: "Server", persona_id: null },
              overview: { cast: [], personas: [], lore: [], activity: { turn_count: 0, recent: [] }, issues: [] },
            }}),
            request: async () => { throw { kind: "network", userMessage: "Offline" }; },
            cancel: () => true,
          };
          const target = { addEventListener() {}, removeEventListener() {} };
          const runtime = authoringModule.createLibraryAuthoringRuntime({
            store, apiClient, localState, router: { current: () => route }, target,
          });
          await Promise.resolve(); await Promise.resolve();
          const restored = structuredClone(store.getSnapshot().library.authoring);
          const accepted = await runtime.save();
          const failed = structuredClone(store.getSnapshot().library.authoring);
          runtime.teardown();
          return {
            restored: { status: restored.status, draft: restored.draft, restored: restored.restored },
            accepted,
            failed: { status: failed.status, draft: failed.draft, error: failed.error },
            draftStillStored: drafts.has("library-authoring:story:4"),
          };
        }""",
        ui_base_url,
    )
    assert result["restored"] == {
        "status": "dirty", "draft": {
            "name": "Recovered", "scenario": "Long draft", "persona_id": 9,
        }, "restored": True,
    }
    assert result["accepted"] is False
    assert result["failed"] == {
        "status": "recoverable-error",
        "draft": {"name": "Recovered", "scenario": "Long draft", "persona_id": 9},
        "error": "Offline",
    }
    assert result["draftStillStored"] is True


def test_story_import_retry_and_branch_use_distinct_owned_operations(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=alpha98-ui2-3f44d1cc71ed`
          );
          const authoringModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui2-3f44d1cc71ed`
          );
          const store = storeModule.createStore();
          let route = {
            destination: "library", segments: ["stories"], query: { mode: "import" },
            canonicalHash: "#/library/stories?mode=import",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          const requests = [];
          let importAttempts = 0;
          const apiClient = {
            get: async () => { throw new Error("unexpected load"); },
            request: async (method, path, options) => {
              requests.push({ method, path, body: options.body ?? null, owner: options.owner });
              if (path === "/api/chats/import" && importAttempts++ === 0) {
                throw { kind: "network", userMessage: "Offline" };
              }
              return { data: path === "/api/chats/import" ? { id: 7 } : { id: 8 } };
            },
            cancel: () => true,
          };
          const navigations = [];
          const router = {
            current: () => route,
            navigate: destination => {
              navigations.push(destination);
              route = {
                ...destination,
                canonicalHash: `#/library/stories?item=${destination.query.item}`,
              };
              store.dispatch({ type: "presentation/replace", slice: "route", value: route });
            },
          };
          const runtime = authoringModule.createLibraryAuthoringRuntime({
            store, apiClient,
            localState: { getDraft: () => null, setDraft() {}, clearDraft() {} },
            router, target: { addEventListener() {}, removeEventListener() {} },
          });
          const archive = { format: "sonder.story.v1", chat: { name: "Imported" } };
          const firstImport = await runtime.importStory(archive);
          const failed = structuredClone(store.getSnapshot().library.authoring);
          const retried = await runtime.retryImport();

          route = {
            destination: "library", segments: ["stories"],
            query: { item: "story:3" },
            canonicalHash: "#/library/stories?item=story%3A3",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          await Promise.resolve(); await Promise.resolve();
          // Resolve the view load through a second runtime whose read is complete.
          runtime.teardown();
          const branchRuntime = authoringModule.createLibraryAuthoringRuntime({
            store,
            apiClient: {
              get: async () => ({ data: {
                kind: "story", id: 3, owner: "story:3", revision: "rev-three",
                document: { name: "Source", scenario: "", persona_id: null },
                overview: { cast: [], personas: [], lore: [], activity: {
                  turn_count: 1, recent: [{ id: 51, idx: 0, created: 1 }],
                }, issues: [] },
              } }),
              request: apiClient.request,
              cancel: () => true,
            },
            localState: { getDraft: () => null, setDraft() {}, clearDraft() {} },
            router, target: { addEventListener() {}, removeEventListener() {} },
          });
          await Promise.resolve(); await Promise.resolve();
          const branched = await branchRuntime.branchStory(51);
          branchRuntime.teardown();
          return {
            firstImport, failed: { status: failed.status, retryAvailable: failed.retryAvailable },
            retried, branched, requests, navigations,
          };
        }""",
        ui_base_url,
    )
    assert result["firstImport"] is False
    assert result["failed"] == {"status": "import-error", "retryAvailable": True}
    assert result["retried"] is True
    assert result["branched"] is True
    assert result["requests"] == [
        {"method": "POST", "path": "/api/chats/import", "body": {
            "data": {"format": "sonder.story.v1", "chat": {"name": "Imported"}},
            }, "owner": "story:import:current"},
        {"method": "POST", "path": "/api/chats/import", "body": {
            "data": {"format": "sonder.story.v1", "chat": {"name": "Imported"}},
            }, "owner": "story:import:current"},
        {"method": "POST", "path": "/api/turns/51/branch", "body": None,
         "owner": "story:3"},
    ]
    assert [row["query"]["item"] for row in result["navigations"]] == [
        "story:7", "story:8",
    ]
