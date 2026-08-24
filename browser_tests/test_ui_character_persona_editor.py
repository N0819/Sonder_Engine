"""Real-browser proof for lossless reusable-person editing."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect


def test_person_editor_field_contract_and_discard_confirmation(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=alpha98-ui6-57d168ae23cf`
          );
          const original = {
            identity: { uid: "char-mara", name: "Mara Venn", aliases: [], pronouns: {} },
            initial_outfit: { wearing: [], state: [], regions: {} },
            simulation: { tier: "mid", temperature: 0.8, sampler: {},
              curiosity: 0.5, offscreen_agent: false },
            embodiment: { visible: { summary: "A rain-dark courier." } },
            psychology: {}, social: {}, competence: {}, knowledge: {},
            initial_state: {}, opening: { first_message: "Evening.", greetings: [] },
          };
          window.__personDiscardCalls = 0;
          const host = document.createElement("div");
          host.id = "person-contract-host";
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document,
            services: {
              localizer: { t: value => value },
              store: { getSnapshot: () => ({ library: {}, settings: { data: {} } }) },
              authoring: {
                stage() {}, save() {},
                discard() { window.__personDiscardCalls += 1; },
                previewAppearance() {}, previewPsychology() {}, previewGreeting() {},
                previewGreetingRecovery() {}, retryPreview() {}, discardPreview() {},
                quickStart() {},
              },
            },
            state: {
              kind: "character", id: 7, mode: "edit", status: "dirty",
              owner: "character:7", draft: structuredClone(original),
            },
          }));
        }""",
        ui_base_url,
    )

    controls = page.locator(
        "#person-contract-host input:not([type=checkbox]), "
        "#person-contract-host select, #person-contract-host textarea"
    )
    assert controls.count() > 0
    assert controls.evaluate_all(
        "nodes => nodes.every(node => node.classList.contains('ui-field__control'))"
    )
    assert page.locator("#person-contract-host .ui-input, #person-contract-host .ui-textarea").count() == 0

    page.get_by_role("button", name="Discard draft").click()
    dialog = page.get_by_role("dialog", name="Discard changes to Mara Venn?")
    expect(dialog).to_be_visible()
    assert page.evaluate("window.__personDiscardCalls") == 0
    dialog.get_by_role("button", name="Keep editing").click()
    expect(dialog).to_have_count(0)
    assert page.evaluate("window.__personDiscardCalls") == 0

    page.get_by_role("button", name="Discard draft").click()
    dialog = page.get_by_role("dialog", name="Discard changes to Mara Venn?")
    dialog.get_by_role("button", name="Discard local changes").click()
    expect(dialog).to_have_count(0)
    assert page.evaluate("window.__personDiscardCalls") == 1


def test_shared_person_sections_keep_all_document_fields_reachable(
    page: Page, ui_base_url: str,
) -> None:
    """Flattening the editor again would hide extension fields in one long form."""

    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=alpha98-ui6-57d168ae23cf`
          );
          const original = {
            identity: { uid: "char-mara", name: "Mara", aliases: [],
              pronouns: { subject: "she", object: "her", possessive: "her" } },
            initial_outfit: { wearing: [], state: [], regions: {} },
            simulation: { tier: "mid", temperature: 0.8, sampler: {},
              curiosity: 0.5, offscreen_agent: false },
            embodiment: { visible: { summary: "Rain-dark coat" }, senses: [],
              scent: "rain", latent: [], extra_parts: [] },
            psychology: { traits: [], values: [] },
            social: { voice: { register: "quiet" } },
            competence: { abilities: [] },
            knowledge: { public_history: "Courier", private_history: [] },
            initial_state: { mood: { label: "watchful" } },
            opening: { first_message: "Evening.", greetings: [] },
            extension_payload: { note: "must survive" },
          };
          let staged = structuredClone(original);
          const services = {
            localizer: { t: value => value },
            store: { getSnapshot: () => ({ library: { personas: [], lorebooks: [], items: [] }, settings: { data: {} } }) },
            authoring: {
              stage: value => { staged = structuredClone(value); },
              discard() {}, save() {}, previewAppearance() {}, previewPsychology() {},
              previewGreeting() {}, previewGreetingRecovery() {}, retryPreview() {},
              discardPreview() {}, quickStart() {},
            },
          };
          const host = document.createElement("div");
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document, services,
            state: { kind: "character", id: 7, mode: "edit", status: "saved",
              owner: "character:7", draft: structuredClone(original) },
          }));
          const labels = [...host.querySelectorAll('.ui-person-editor__nav [role="tab"]')]
            .map(button => button.textContent.trim());
          const more = host.querySelector(".ui-person-editor__more");
          if (more) more.open = true;
          const auxiliary = [...(more?.querySelectorAll("button") || [])]
            .map(button => button.textContent.trim());
          const additional = [...host.querySelectorAll(".ui-person-editor__nav button")]
            .find(button => button.textContent.trim() === "Additional fields");
          additional?.click();
          const note = host.querySelector('[data-schema-path="extension_payload.note"]');
          if (note) {
            note.value = "kept and edited";
            note.dispatchEvent(new Event("input", { bubbles: true }));
          }
          const activePanel = host.querySelector('.ui-person-editor__panel:not([hidden])')?.dataset.editorSection;
          const moreLabel = more?.querySelector("summary")?.textContent.trim() || "";
          host.remove();
          return { labels, auxiliary, staged, activePanel, moreLabel };
        }""",
        ui_base_url,
    )

    assert result["labels"] == [
        "Basics", "Appearance", "History", "Inner life", "Opening",
        "Simulation",
    ]
    assert result["auxiliary"] == ["Start a Story", "Additional fields", "Advanced"]
    assert result["activePanel"] == "additional"
    assert result["moreLabel"] == "More · Additional fields"
    assert result["staged"]["extension_payload"]["note"] == "kept and edited"


def test_person_editor_semantic_field_registry_is_plain_and_lossless(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=alpha98-ui6-57d168ae23cf`
          );
          const original = {
            identity: { uid: "char-mara", name: "Mara", aliases: [], pronouns: {} },
            initial_outfit: { wearing: [], state: [], regions: {} },
            simulation: { tier: "mid", temperature: 0.8, sampler: { top_p: 0.9 },
              curiosity: 0.5, offscreen_agent: false },
            embodiment: {
              visible: { summary: "Rain-dark coat" },
              interoception: { acuity: 0.5, pain_sensitivity: 0.6,
                fatigue_sensitivity: 0.4, pleasure_sensitivity: 0.7 },
            },
            psychology: {
              drive: { essence: "Deliver the letter", expression: "", taboo: "" },
              traits: [], values: [], capacity: "focused",
            },
            social: {}, competence: {}, knowledge: {},
            initial_state: {
              mood: { label: "watchful", valence: 0.1, arousal: 0.4 },
              hedonic: { pain: 0, pleasure: 0, source: "" },
            },
            opening: { first_message: "Evening.", greetings: [] },
            extension_payload: { note: "must survive", nested: { exact: true } },
          };
          let staged = structuredClone(original);
          const host = document.createElement("div");
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document,
            services: {
              localizer: { t: value => value },
              store: { getSnapshot: () => ({ library: {}, settings: { data: {} } }) },
              authoring: {
                stage(value) { staged = structuredClone(value); }, save() {}, discard() {},
                previewAppearance() {}, previewPsychology() {}, previewGreeting() {},
                previewGreetingRecovery() {}, retryPreview() {}, discardPreview() {},
                quickStart() {},
              },
            },
            state: { kind: "character", id: 7, mode: "edit", status: "saved",
              owner: "character:7", draft: structuredClone(original) },
          }));
          const labels = [...host.querySelectorAll(".ui-authoring-field__label")]
            .map(label => label.textContent.trim());
          const allText = host.textContent;
          const curiosity = host.querySelector('[data-schema-path="simulation.curiosity"]');
          curiosity.value = "0.7";
          curiosity.dispatchEvent(new Event("input", { bubbles: true }));
          const result = {
            labels, allText, staged,
            curiosity: { min: curiosity.min, max: curiosity.max, step: curiosity.step,
              describedBy: curiosity.getAttribute("aria-describedby") },
          };
          host.remove();
          return result;
        }""",
        ui_base_url,
    )

    for label in (
        "Creativity", "Curiosity", "Background activity", "Starting mood",
        "Pain sensitivity", "Sampling overrides",
    ):
        assert label in result["labels"]
    for raw_label in ("Top p", "Offscreen agent", "Hedonic"):
        assert raw_label not in result["labels"]
    assert result["curiosity"]["min"] == "0"
    assert result["curiosity"]["max"] == "1"
    assert result["curiosity"]["step"] == "0.05"
    assert result["curiosity"]["describedBy"]
    assert result["staged"]["simulation"]["curiosity"] == 0.7
    assert result["staged"]["simulation"]["sampler"] == {"top_p": 0.9}
    assert result["staged"]["extension_payload"] == {
        "note": "must survive", "nested": {"exact": True},
    }


def test_save_reveals_and_focuses_invalid_field_in_another_section(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=alpha98-ui6-57d168ae23cf`
          );
          let saves = 0;
          const host = document.createElement("div");
          document.body.append(host);
          host.append(editorModule.createPersonEditor({
            document,
            services: {
              localizer: { t: value => value },
              store: { getSnapshot: () => ({ library: {}, settings: { data: {} } }) },
              authoring: {
                stage() {}, save() { saves += 1; }, discard() {},
                previewAppearance() {}, previewPsychology() {}, previewGreeting() {},
                previewGreetingRecovery() {},
              },
            },
            state: {
              kind: "character", id: 91, mode: "edit", status: "saved",
              owner: "character:91",
              draft: {
                identity: { uid: "char-91", name: "Mara", aliases: [], pronouns: {} },
                initial_outfit: { wearing: ["coat"] },
                embodiment: { visible: {} }, knowledge: {}, psychology: {}, social: {},
                initial_state: {}, opening: { greetings: [] }, simulation: {},
              },
            },
          }));
          const wearing = host.querySelector('[data-schema-path="initial_outfit.wearing"]');
          wearing.value = "not valid JSON";
          wearing.dispatchEvent(new Event("change", { bubbles: true }));
          [...host.querySelectorAll('[role="tab"]')]
            .find(tab => tab.textContent.trim() === "Inner life").click();
          host.querySelector("form").requestSubmit();
          const result = {
            saves,
            active: host.querySelector('.ui-person-editor__panel:not([hidden])')?.dataset.editorSection,
            focusedPath: document.activeElement?.dataset?.schemaPath,
          };
          host.remove();
          return result;
        }""",
        ui_base_url,
    )
    assert result == {
        "saves": 0,
        "active": "appearance",
        "focusedPath": "initial_outfit.wearing",
    }


def test_character_editor_preserves_unknown_fields_through_advanced_json(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const editorModule = await import(
            `${base}/static/js/ui-next/library-editors/character-persona.js?release=alpha98-ui6-57d168ae23cf`
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
            store: { getSnapshot: () => ({
              library: {
                personas: [{ id: 8, name: "Mira" }],
                lorebooks: [{ id: 12, name: "Rain Atlas" }],
                items: [],
              },
              settings: { data: { ui_language: "ja" } },
            }) },
            authoring: {
              stage: value => { staged = structuredClone(value); },
              quickStart: options => { quickStart = structuredClone(options); },
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
          const quick = host.querySelector(".ui-authoring-quick-start");
          quick.querySelector('select[id^="ui-quick-persona-"]').value = "8";
          quick.querySelectorAll("select")[2].value = "12";
          quick.querySelector(".ui-authoring-quick-start__known input").click();
          quick.querySelector("details summary").click();
          quick.querySelector('input[aria-label="Prepare a lived location"]').click();
          const locationBrief = quick.querySelector(".ui-lived-location__content textarea");
          locationBrief.value = "A rain archive";
          locationBrief.dispatchEvent(new Event("input", { bubbles: true }));
          const historyRoute = quick.querySelector('select[aria-label^="History route for"]');
          historyRoute.value = "resident";
          historyRoute.dispatchEvent(new Event("change", { bubbles: true }));
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
    assert result["quickStart"] == {
        "personaId": 8,
        "greetingIndex": 0,
        "lorebookId": 12,
        "alreadyKnown": True,
        "language": "ja",
        "livedLocation": {
            "enabled": True,
            "brief": "A rain archive",
            "horizon_hours": 0,
            "active_tail_hours": 0,
            "generate_history": False,
            "character_history": {"mode": "resident", "brief": ""},
        },
    }


def test_create_preview_failure_retry_discard_and_accept_are_lossless(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui6-57d168ae23cf`);
          const runtimeModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui6-57d168ae23cf`
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
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui6-57d168ae23cf`);
          const runtimeModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui6-57d168ae23cf`
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
          const started = await runtime.quickStart({ personaId: 8, greetingIndex: 0 });
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
    assert result["calls"][1]["body"] == {
        "persona_id": 8,
        "greeting_index": 0,
        "already_known": False,
        "language": "en",
    }
    assert result["navigation"] == {"destination": "play", "query": {"chat": "71"}}


def test_story_card_override_loads_and_saves_its_story_owned_document(
    page: Page, ui_base_url: str,
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async base => {
          const storeModule = await import(`${base}/static/js/ui-next/store.js?release=alpha98-ui6-57d168ae23cf`);
          const runtimeModule = await import(
            `${base}/static/js/ui-next/library-authoring-runtime.js?release=alpha98-ui6-57d168ae23cf`
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
