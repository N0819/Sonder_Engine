"""Real-browser contracts for Library authoring ownership and recovery."""

from __future__ import annotations

from playwright.sync_api import Page


def test_authoring_runtime_preserves_drafts_and_rejects_late_save(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(
            `${base}/static/js/ui-next/store.js?release=wp07.1`
          );
          const authoringModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=wp07.1`
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
            `${base}/static/js/ui-next/store.js?release=wp07.1`
          );
          const authoringModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=wp07.1`
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
