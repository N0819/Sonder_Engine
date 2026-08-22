"""Behavioral contracts for the build-free replacement runtime."""

from __future__ import annotations

from playwright.sync_api import Page


def test_release_module_is_importable_without_classic_host_scripts(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const module = await import(`${base}/static/js/ui-next/release.js?release=wp02.1`);
          return {
            release: module.MODULE_RELEASE,
            hasClassicState: Object.hasOwn(window, "S"),
            hasReleaseCheck: typeof module.assertReleaseModules === "function",
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "release": "wp02.1",
        "hasClassicState": False,
        "hasReleaseCheck": True,
    }


def test_runtime_rejects_a_mixed_release_before_boot(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const runtime = await import(
            `${base}/static/js/ui-next/bootstrap.js?release=wp02.1`
          );
          try {
            await runtime.loadRuntimeModules(async path => ({
              MODULE_RELEASE: path.includes("api.js") ? "wp01" : "wp02.1",
            }));
          } catch (error) {
            return {
              name: error.name,
              kind: error.kind,
              moduleName: error.moduleName,
              expected: error.expected,
              received: error.received,
            };
          }
          return null;
        }""",
        ui_base_url,
    )
    assert result == {
        "name": "MixedReleaseError",
        "kind": "mixed-release",
        "moduleName": "api",
        "expected": "wp02.1",
        "received": "wp01",
    }


def test_reboot_replaces_runtime_listeners_instead_of_accumulating_them(
    page: Page, ui_base_url: str
) -> None:
    page.goto(f"{ui_base_url}/static/ui-next-lab.html")
    result = page.evaluate(
        """async (base) => {
          const runtime = await import(
            `${base}/static/js/ui-next/bootstrap.js?release=wp02.1`
          );
          const listeners = new Map();
          let added = 0;
          let removed = 0;
          const target = {
            addEventListener(type, listener) {
              added += 1;
              listeners.set(`${type}:${added}`, listener);
            },
            removeEventListener(type, listener) {
              removed += 1;
              for (const [key, value] of listeners) {
                if (key.startsWith(`${type}:`) && value === listener) {
                  listeners.delete(key);
                  break;
                }
              }
            },
            dispatchEvent() {},
          };
          const importer = async () => ({ MODULE_RELEASE: "wp02.1" });
          const firstRoot = { dataset: {} };
          const secondRoot = { dataset: {} };
          await runtime.bootRuntime({ target, root: firstRoot, importModule: importer });
          const second = await runtime.bootRuntime({
            target,
            root: secondRoot,
            importModule: importer,
          });
          const afterReboot = {
            added,
            removed,
            live: listeners.size,
            firstState: firstRoot.dataset.uiNextState,
            secondState: secondRoot.dataset.uiNextState,
          };
          second.teardown();
          return {
            afterReboot,
            afterStop: {
              removed,
              live: listeners.size,
              state: secondRoot.dataset.uiNextState,
            },
          };
        }""",
        ui_base_url,
    )
    assert result == {
        "afterReboot": {
            "added": 4,
            "removed": 2,
            "live": 2,
            "firstState": "stopped",
            "secondState": "ready",
        },
        "afterStop": {"removed": 4, "live": 0, "state": "stopped"},
    }
