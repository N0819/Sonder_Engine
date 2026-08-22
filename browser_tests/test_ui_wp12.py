"""Browser contracts for the WP12 theme and extension compatibility gate."""

from __future__ import annotations

from playwright.sync_api import Page


def test_v2_facade_versions_every_slot_and_tears_down_by_owner(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createExtensionRegistry } = await import(
            `${base}/static/js/ui-next/extensions.js?release=wp12.1`
          );
          const registry = createExtensionRegistry({
            apiClient: { request: async request => ({ data: request.url, status: 200 }) },
          });
          const facade = registry.facade("fixture-v2");
          let tornDown = 0;
          facade.registerDestination({ id: "desk", title: "Desk", render() {} });
          facade.registerLibraryType({ id: "relic", title: "Relic", render() {} });
          facade.registerPlayTool({ id: "oracle", title: "Oracle", render() {} });
          facade.registerSettingsSection({ id: "prefs", title: "Preferences", render() {} });
          facade.registerTaskProvider({ id: "sync", title: "Sync", provide() {} });
          facade.addTeardown(() => { tornDown += 1; });
          const before = registry.snapshot();
          registry.unregisterOwner("fixture-v2", { retire: true });
          return {
            apiVersion: facade.apiVersion,
            owner: facade.id,
            tokens: facade.tokens,
            before: Object.fromEntries([
              "destination", "library-type", "play-tool", "addon-settings", "task-provider",
            ].map(kind => [kind, before[kind].map(entry => `${entry.owner}:${entry.id}`)])),
            retired: registry.isRetired("fixture-v2"),
            tornDown,
            after: Object.values(registry.snapshot()).flat().length,
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "apiVersion": 2,
        "owner": "fixture-v2",
        "tokens": {
            "canvas": "--ui-color-canvas",
            "surface": "--ui-color-surface-muted",
            "text": "--ui-color-text",
            "border": "--ui-color-border",
            "accent": "--ui-color-interactive",
            "danger": "--ui-color-danger",
        },
        "before": {
            "destination": ["fixture-v2:desk"],
            "library-type": ["fixture-v2:relic"],
            "play-tool": ["fixture-v2:oracle"],
            "addon-settings": ["fixture-v2:prefs"],
            "task-provider": ["fixture-v2:sync"],
        },
        "retired": True,
        "tornDown": 1,
        "after": 0,
    }


def test_v1_global_remains_adapter_only_while_modules_receive_v2(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createExtensionRegistry } = await import(
            `${base}/static/js/ui-next/extensions.js?release=wp12.1`
          );
          const { createV1Adapter, installV1Adapter } = await import(
            `${base}/static/js/ui-next/extensions-v1.js?release=wp12.1`
          );
          const registry = createExtensionRegistry({
            apiClient: { request: async () => ({ data: null, status: 200 }) },
          });
          const uninstall = installV1Adapter(createV1Adapter(registry));
          const moduleFacade = registry.facade("module-owner");
          const answer = {
            globalVersion: window.Sonder.apiVersion,
            moduleVersion: moduleFacade.apiVersion,
            globalCanRegisterLegacy: typeof window.Sonder.registerView,
            moduleCanRegisterLegacy: typeof moduleFacade.registerView,
            classicGlobal: Object.hasOwn(window, "S"),
          };
          uninstall();
          answer.adapterRemoved = !Object.hasOwn(window, "Sonder");
          return answer;
        }""",
        ui_base_url,
    )
    assert result == {
        "globalVersion": 1,
        "moduleVersion": 2,
        "globalCanRegisterLegacy": "function",
        "moduleCanRegisterLegacy": "undefined",
        "classicGlobal": False,
        "adapterRemoved": True,
    }


def test_v2_play_and_library_slots_mount_in_their_destination_and_retire_safely(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const { createExtensionRegistry } = await import(
            `${base}/static/js/ui-next/extensions.js?release=wp12.1`
          );
          const { createExtensionHost } = await import(
            `${base}/static/js/ui-next/extension-host.js?release=wp12.1`
          );
          const registry = createExtensionRegistry({
            apiClient: { request: async () => ({ data: null, status: 200 }) },
          });
          const navigations = [];
          let current = { destination: "play", segments: [], query: {} };
          const services = {
            registry,
            localizer: { t: value => value },
            notices: { problem: value => navigations.push({ notice: value.message }) },
            router: {
              current: () => current,
              serialize: route => `#/${route.destination}?kind=${route.query.kind}`,
              navigate: route => { navigations.push(route); current = route; },
            },
          };
          const host = createExtensionHost({ services, document });
          registry.facade("fixture-v2").registerPlayTool({
            id: "oracle", title: "Oracle", render(container) {
              container.textContent = "Oracle ready";
              return () => { container.dataset.tornDown = "true"; };
            },
          });
          registry.facade("fixture-v2").registerLibraryType({
            id: "relic", title: "Relics", render(container) {
              container.textContent = "Relic shelf";
            },
          });
          const playLaunchers = document.createElement("main");
          host.decorate({ route: current, view: playLaunchers });
          current = {
            destination: "play", segments: [],
            query: { extension: "fixture-v2", view: "oracle", kind: "play-tool" },
          };
          const playMount = document.createElement("main");
          host.decorate({ route: current, view: playMount });
          const playText = playMount.textContent;
          current = { destination: "library", segments: [], query: {} };
          const libraryLaunchers = document.createElement("main");
          host.decorate({ route: current, view: libraryLaunchers });
          current = {
            destination: "library", segments: [],
            query: { extension: "fixture-v2", view: "relic", kind: "library-type" },
          };
          const libraryMount = document.createElement("main");
          host.decorate({ route: current, view: libraryMount });
          const libraryText = libraryMount.textContent;
          registry.unregisterOwner("fixture-v2", { retire: true });
          host.teardown();
          return {
            playLauncher: playLaunchers.textContent,
            playText,
            libraryLauncher: libraryLaunchers.textContent,
            libraryText,
            retiredRoute: navigations.at(-1),
          };
        }""",
        ui_base_url,
    )
    assert "Oracle" in result["playLauncher"]
    assert "Oracle ready" in result["playText"]
    assert "Relics" in result["libraryLauncher"]
    assert "Relic shelf" in result["libraryText"]
    assert result["retiredRoute"] == {
        "destination": "library",
        "segments": [],
    }
