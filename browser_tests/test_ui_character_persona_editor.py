"""Real-browser proof for lossless reusable-person editing."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def test_character_editor_preserves_unknown_fields_through_advanced_json(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=wp07.1`
          );
          const original = {
            identity: { uid: "char-a", name: "Asha", aliases: ["Ash"],
              pronouns: { subject: "she", object: "her", possessive: "her" } },
            embodiment: { visible: { summary: "Copper hair" } },
            knowledge: { public_history: "Archive keeper" },
            psychology: { drive: { essence: "Keep the record", taboo: "Erase a witness" } },
            opening: { first_message: "Welcome.", greetings: [{ prose: "Welcome." }] },
            extension_payload: { nested: [1, { exact: true }] },
          };
          let staged = null;
          let quickStart = null;
          const services = {
            localizer: { t: value => value },
            store: { getSnapshot: () => ({ library: { library: { items: [
              { kind: "persona", id: 8, name: "Mira", archived: false },
            ] } } }) },
            authoring: {
              stage: value => { staged = structuredClone(value); },
              quickStart: (persona, greeting) => { quickStart = { persona, greeting }; },
            },
          };
          const host = document.createElement("div");
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document, services,
            state: { kind: "character", id: 4, mode: "edit", status: "saved",
              draft: structuredClone(original) },
          }));
          const name = host.querySelector('[name="identity.name"]');
          name.value = "Asha Vale";
          name.dispatchEvent(new Event("input", { bubbles: true }));
          const drive = host.querySelector('[data-schema-path="psychology.drive.essence"]');
          drive.value = "Protect the living record";
          drive.dispatchEvent(new Event("input", { bubbles: true }));
          const afterForm = structuredClone(staged);
          const advanced = host.querySelector('[name="advanced_json"]');
          const parsed = JSON.parse(advanced.value);
          parsed.extension_payload.nested[1].exact = "still here";
          advanced.value = JSON.stringify(parsed, null, 2);
          host.querySelector('[data-apply-advanced]').click();
          const afterAdvanced = structuredClone(staged);
          const heading = host.querySelector(".ui-authoring-form__header h2")?.textContent;
          const more = host.querySelector(".ui-action-more");
          more.open = true;
          const secondaryTools = more.querySelectorAll(".ui-action-more__menu button").length;
          const stableIdentityLocked = host.querySelector('[data-schema-path="identity.uid"]')?.disabled;
          host.querySelector(".ui-authoring-quick-start .ui-button--primary").click();
          host.remove();
          return { afterForm, afterAdvanced, heading, secondaryTools, stableIdentityLocked, quickStart };
        }""",
        ui_base_url,
    )
    assert result["afterForm"]["identity"]["name"] == "Asha Vale"
    assert result["afterForm"]["psychology"]["drive"] == {
        "essence": "Protect the living record",
        "taboo": "Erase a witness",
    }
    assert result["afterForm"]["extension_payload"] == {
        "nested": [1, {"exact": True}],
    }
    assert result["afterAdvanced"]["extension_payload"] == {
        "nested": [1, {"exact": "still here"}],
    }
    assert result["heading"] == "Asha Vale"
    assert result["secondaryTools"] == 2
    assert result["stableIdentityLocked"] is True
    assert result["quickStart"] == {"persona": "8", "greeting": "0"}


def test_create_preview_failure_retry_discard_and_accept_are_lossless(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=wp07.1`);
          const runtimeModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=wp07.1`
          );
          const store = storeModule.createStore();
          const route = {
            destination: "library", segments: ["characters"],
            query: { mode: "create", session: "test-session" },
            canonicalHash: "#/library/characters?mode=create&session=test-session",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          const requests = [];
          const apiClient = {
            get: async path => ({ data: { sheet: {
              identity: { uid: "char-new", name: "Unnamed", aliases: [], pronouns: {} },
              opening: {}, extension_payload: { exact: [1, 2] },
            } } }),
            request: (method, path, options) => new Promise((resolve, reject) => {
              requests.push({ method, path, options, resolve, reject });
            }),
            cancel: () => true,
          };
          const drafts = new Map();
          const localState = {
            getDraft: (type, owner) => drafts.get(`${type}:${owner}`) ?? null,
            setDraft: (type, owner, value) => drafts.set(`${type}:${owner}`, value),
            clearDraft: (type, owner) => drafts.delete(`${type}:${owner}`),
          };
          const target = { addEventListener() {}, removeEventListener() {} };
          const navigations = [];
          const router = {
            current: () => route,
            navigate: value => navigations.push(value),
          };
          const runtime = runtimeModule.createLibraryAuthoringRuntime({
            store, apiClient, localState, router, target,
          });
          await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
          const draft = structuredClone(store.getSnapshot().library.authoring.draft);
          draft.identity.name = "Draft keeper";
          draft.draft_only = { survives: true };
          runtime.stage(draft);
          const failed = runtime.previewGenerate("storm guide");
          requests[0].reject(new Error("provider offline"));
          const failedResult = await failed;
          const afterFailure = structuredClone(store.getSnapshot().library.authoring);
          const retried = runtime.retryPreview();
          const generated = structuredClone(draft);
          generated.identity.name = "Generated keeper";
          generated.generated_only = { review: true };
          requests[1].resolve({ data: { sheet: generated } });
          const retryResult = await retried;
          const afterRetry = structuredClone(store.getSnapshot().library.authoring);
          const discarded = runtime.discardPreview();
          const afterDiscard = structuredClone(store.getSnapshot().library.authoring);
          const accepted = runtime.save();
          requests[2].resolve({ data: { id: 91, sheet: afterDiscard.draft } });
          const acceptedResult = await accepted;
          runtime.teardown();
          return {
            owner: afterFailure.owner,
            failedResult,
            failureStatus: afterFailure.status,
            failureDraft: afterFailure.draft,
            retryResult,
            retryDraft: afterRetry.draft,
            preview: afterRetry.preview,
            discarded,
            discardDraft: afterDiscard.draft,
            saveRequest: {
              method: requests[2].method, path: requests[2].path,
              body: requests[2].options.body,
            },
            acceptedResult,
            navigation: navigations[0],
          };
        }""",
        ui_base_url,
    )
    assert result["owner"] == "character:create:test-session"
    assert result["failedResult"] is False
    assert result["failureStatus"] == "generation-error"
    assert result["failureDraft"]["draft_only"] == {"survives": True}
    assert result["retryResult"] is True
    assert result["retryDraft"]["generated_only"] == {"review": True}
    assert result["preview"] == {"task": "generate"}
    assert result["discarded"] is True
    assert result["discardDraft"]["draft_only"] == {"survives": True}
    assert "generated_only" not in result["discardDraft"]
    assert result["saveRequest"] == {
        "method": "POST",
        "path": "/api/characters",
        "body": {"sheet": result["discardDraft"]},
    }
    assert result["acceptedResult"] is True
    assert result["navigation"]["query"] == {"item": "character:91"}


def test_quick_start_saves_the_owned_draft_before_opening_play(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=wp07.1`);
          const runtimeModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=wp07.1`
          );
          const store = storeModule.createStore();
          const route = {
            destination: "library", segments: ["characters"],
            query: { item: "character:4", mode: "edit" },
            canonicalHash: "#/library/characters?item=character%3A4&mode=edit",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          const original = {
            identity: { uid: "char-4", name: "Asha" },
            opening: { greetings: [{ prose: "Welcome." }] },
          };
          const calls = [];
          const apiClient = {
            get: async () => ({ data: {
              owner: "character:4", kind: "character", id: 4,
              revision: "rev-4", document: structuredClone(original),
            } }),
            request: async (method, path, options) => {
              calls.push({ method, path, body: structuredClone(options.body) });
              if (path.endsWith("/start")) return { data: { chat_id: 71, turn_id: 1 } };
              return { data: {
                owner: "character:4", kind: "character", id: 4,
                revision: "rev-5", document: structuredClone(options.body.sheet),
              } };
            },
            cancel: () => true,
          };
          const navigations = [];
          const runtime = runtimeModule.createLibraryAuthoringRuntime({
            store, apiClient,
            localState: { getDraft: () => null, setDraft() {}, clearDraft() {} },
            router: { current: () => route, navigate: value => navigations.push(value) },
            target: { addEventListener() {}, removeEventListener() {} },
          });
          await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
          const draft = structuredClone(original);
          draft.identity.name = "Asha Vale";
          runtime.stage(draft);
          const started = await runtime.quickStart(8, 0);
          runtime.teardown();
          return { started, calls, navigation: navigations[0] };
        }""",
        ui_base_url,
    )
    assert result["started"] is True
    assert [call["path"] for call in result["calls"]] == [
        "/api/characters/4", "/api/characters/4/start",
    ]
    assert result["calls"][0]["body"]["sheet"]["identity"]["name"] == "Asha Vale"
    assert result["calls"][1]["body"] == {"persona_id": 8, "greeting_index": 0}
    assert result["navigation"] == {"destination": "play", "query": {"chat": "71"}}


def test_story_card_override_loads_and_saves_its_story_owned_document(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=wp07.1`);
          const runtimeModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=wp07.1`
          );
          const store = storeModule.createStore();
          const route = {
            destination: "library", segments: ["characters"],
            query: { item: "character:4", mode: "story-card", story: "12" },
            canonicalHash: "#/library/characters?item=character%3A4&mode=story-card&story=12",
          };
          store.dispatch({ type: "presentation/replace", slice: "route", value: route });
          const card = {
            identity: { uid: "char-4", name: "Asha" },
            psychology: { drive: { essence: "Story-only drive" } },
          };
          const calls = [];
          const apiClient = {
            get: async (path, options) => {
              calls.push({ method: "GET", path, owner: options.owner });
              return { data: {
                chat: { id: 12, name: "Lantern Story" },
                participants: [{ id: 4, name: "Asha", sheet: JSON.stringify(card), card_source: "chat" }],
              } };
            },
            request: async (method, path, options) => {
              calls.push({ method, path, owner: options.owner, body: structuredClone(options.body) });
              return { data: { ok: true, sheet: options.body.sheet, card_source: "chat" } };
            },
            cancel: () => true,
          };
          const runtime = runtimeModule.createLibraryAuthoringRuntime({
            store, apiClient,
            localState: { getDraft: () => null, setDraft() {}, clearDraft() {} },
            router: { current: () => route, navigate() {} },
            target: { addEventListener() {}, removeEventListener() {} },
          });
          await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
          const loaded = structuredClone(store.getSnapshot().library.authoring);
          const draft = structuredClone(loaded.draft);
          draft.psychology.drive.essence = "Changed only here";
          runtime.stage(draft);
          const saved = await runtime.save();
          const final = structuredClone(store.getSnapshot().library.authoring);
          runtime.teardown();
          return {
            owner: loaded.owner,
            storyName: loaded.overview.story_name,
            saved,
            calls,
            final: { status: final.status, drive: final.draft.psychology.drive.essence },
          };
        }""",
        ui_base_url,
    )
    assert result["owner"] == "story-character:12:4"
    assert result["storyName"] == "Lantern Story"
    assert result["saved"] is True
    assert result["calls"] == [
        {"method": "GET", "path": "/api/chats/12", "owner": "story-character:12:4"},
        {
            "method": "PUT",
            "path": "/api/chats/12/characters/4/card",
            "owner": "story-character:12:4",
            "body": {"sheet": {
                "identity": {"uid": "char-4", "name": "Asha"},
                "psychology": {"drive": {"essence": "Changed only here"}},
            }},
        },
    ]
    assert result["final"] == {"status": "saved", "drive": "Changed only here"}
