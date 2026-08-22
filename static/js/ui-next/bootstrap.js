import { assertReleaseModules } from "./release.js?release=wp02.1";

export const MODULE_RELEASE = "wp02.1";

const SERVICE_PATHS = Object.freeze({
  api: "./api.js?release=wp02.1",
  errors: "./errors.js?release=wp02.1",
  store: "./store.js?release=wp02.1",
  router: "./router.js?release=wp02.1",
  localization: "./localization.js?release=wp02.1",
  content: "./content.js?release=wp02.1",
  tasks: "./tasks.js?release=wp02.1",
  notices: "./notices.js?release=wp02.1",
  diagnostics: "./diagnostics.js?release=wp02.1",
  storage: "./storage.js?release=wp02.1",
  credentials: "./credentials.js?release=wp02.1",
  savePolicy: "./save-policy.js?release=wp02.1",
  extensions: "./extensions.js?release=wp02.1",
  extensionsV1: "./extensions-v1.js?release=wp02.1",
});

let activeTeardown = null;

export async function loadRuntimeModules(importModule = path => import(path)) {
  const entries = await Promise.all(Object.entries(SERVICE_PATHS).map(
    async ([name, path]) => [name, await importModule(path)]
  ));
  return assertReleaseModules(Object.fromEntries(entries), MODULE_RELEASE);
}

function installErrorBoundary(target, root, onDiagnostic) {
  const report = (kind, error) => {
    root.dataset.uiNextState = "failed";
    onDiagnostic?.({ kind, error });
    target.dispatchEvent(new CustomEvent("sonder:runtime-error", {
      detail: {
        kind,
        message: "The interface stopped unexpectedly. Your saved stories were not changed.",
      },
    }));
  };
  const onError = event => report("runtime", event.error);
  const onRejection = event => report("promise", event.reason);
  target.addEventListener("error", onError);
  target.addEventListener("unhandledrejection", onRejection);
  return () => {
    target.removeEventListener("error", onError);
    target.removeEventListener("unhandledrejection", onRejection);
  };
}

export async function bootRuntime(options = {}) {
  activeTeardown?.();
  activeTeardown = null;

  const target = options.target || window;
  const root = options.root || document.documentElement;
  const modules = await loadRuntimeModules(options.importModule);
  const cleanups = [installErrorBoundary(target, root, options.onDiagnostic)];

  root.dataset.uiNextRelease = MODULE_RELEASE;
  root.dataset.uiNextState = "ready";
  root.dataset.uiNextReady = "true";

  let done = false;
  activeTeardown = () => {
    if (done) return;
    done = true;
    for (const cleanup of cleanups.reverse()) cleanup?.();
    delete root.dataset.uiNextReady;
    root.dataset.uiNextState = "stopped";
    if (activeTeardown) activeTeardown = null;
  };

  return { modules, teardown: activeTeardown };
}
