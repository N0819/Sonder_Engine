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
            opening: { first_message: "Welcome." },
            extension_payload: { nested: [1, { exact: true }] },
          };
          let staged = null;
          const services = {
            localizer: { t: value => value },
            authoring: { stage: value => { staged = structuredClone(value); } },
          };
          const host = document.createElement("div");
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document, services,
            state: { kind: "character", id: 4, status: "saved",
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
          host.remove();
          return { afterForm, afterAdvanced };
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
