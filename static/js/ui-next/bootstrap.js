import { assertReleaseModules } from "./release.js?release=wp03.1";

export const MODULE_RELEASE = "wp03.1";

// UI_CATALOG_START: fatal boundary copy is deliberately stack-free.
const RUNTIME_FAILURE_MESSAGE = "The interface stopped unexpectedly. Your saved stories were not changed.";
// UI_CATALOG_END

const SERVICE_PATHS = Object.freeze({
  api: "./api.js?release=wp03.1",
  errors: "./errors.js?release=wp03.1",
  store: "./store.js?release=wp03.1",
  router: "./router.js?release=wp03.1",
  localization: "./localization.js?release=wp03.1",
  content: "./content.js?release=wp03.1",
  tasks: "./tasks.js?release=wp03.1",
  notices: "./notices.js?release=wp03.1",
  diagnostics: "./diagnostics.js?release=wp03.1",
  storage: "./storage.js?release=wp03.1",
  credentials: "./credentials.js?release=wp03.1",
  savePolicy: "./save-policy.js?release=wp03.1",
  extensions: "./extensions.js?release=wp03.1",
  extensionsV1: "./extensions-v1.js?release=wp03.1",
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
        message: RUNTIME_FAILURE_MESSAGE,
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

function harnessElements(documentRef) {
  return {
    status: documentRef?.querySelector?.("[data-runtime-status]"),
    detail: documentRef?.querySelector?.("[data-runtime-detail]"),
    diagnosticsToggle: documentRef?.querySelector?.("[data-runtime-diagnostics]"),
    diagnosticsOutput: documentRef?.querySelector?.("[data-runtime-diagnostic-output]"),
  };
}

function setHarnessStatus(elements, status, detail = "") {
  if (elements.status) elements.status.textContent = status;
  if (elements.detail) elements.detail.textContent = detail;
}

function settingsProjection(bootstrap) {
  const allowed = [
    "providers",
    "provider_presets",
    "roles",
    "role_fallbacks",
    "sampler_keys",
    "default_samplers",
    "agent_models",
    "max_output_tokens",
    "max_output_tokens_bounds",
    "reasoning_effort",
    "reasoning_effort_levels",
    "openrouter_routing",
    "nsfw_enabled",
    "attire_beneath",
    "director_fanout_parallel",
    "affect_habituation",
    "backdrops_enabled",
    "backdrop_continuity",
    "ambience",
    "auto_promote",
    "language_packs",
    "ui_language",
    "ui_direction",
    "language_error",
  ];
  return Object.fromEntries(
    allowed.filter(key => Object.hasOwn(bootstrap, key)).map(key => [key, bootstrap[key]]),
  );
}

function extensionBootstrapProjection(bootstrap) {
  const credentialField = /^(password|passphrase|token|api_?key|secret|session|cookie|join_?code|authorization)$/i;
  return Object.fromEntries(
    Object.entries(bootstrap).filter(([key]) => !credentialField.test(key)),
  );
}

function applyLocalAppearance(root, appearance) {
  const safe = appearance && typeof appearance === "object" ? appearance : {};
  if (safe.theme) root.dataset.theme = String(safe.theme);
  if (safe.density) root.dataset.density = String(safe.density);
  if (safe.motion) root.dataset.motion = String(safe.motion);
}

function replaceServerSlice(store, slice, value) {
  store.dispatch({ type: "server/replace", slice, value });
}

function replacePresentationSlice(store, slice, value) {
  store.dispatch({ type: "presentation/replace", slice, value });
}

async function startHostRuntime({ modules, target, root, options, cleanups }) {
  const documentRef = options.document || root.ownerDocument || document;
  const harness = harnessElements(documentRef);
  setHarnessStatus(harness, "Loading runtime services…", "Reading the current engine state.");

  const store = modules.store.createStore();
  cleanups.push(() => store.destroy());

  let diagnostics;
  diagnostics = modules.diagnostics.createDiagnostics({
    enabled: false,
    onChange: () => {
      const snapshot = diagnostics.snapshot();
      replacePresentationSlice(store, "diagnostics", {
        status: "ready",
        enabled: diagnostics.isEnabled(),
        entries: snapshot,
      });
      if (harness.diagnosticsOutput && !harness.diagnosticsOutput.hidden) {
        harness.diagnosticsOutput.textContent = JSON.stringify(snapshot, null, 2);
      }
    },
  });

  const tasks = modules.tasks.createTaskService({
    onChange: items => replacePresentationSlice(
      store,
      "tasks",
      { status: "ready", items },
    ),
  });
  const notices = modules.notices.createNoticeService({
    onChange: items => replacePresentationSlice(
      store,
      "notices",
      { status: "ready", items },
    ),
  });
  const localState = modules.storage.createLocalState({
    storage: options.storage || target.localStorage,
    onError: error => diagnostics.record({ kind: error.kind, message: error.message }),
  });
  applyLocalAppearance(root, localState.snapshot().appearance);
  replacePresentationSlice(store, "appearance", {
    status: "ready",
    ...localState.snapshot().appearance,
  });

  let loginRequested = false;
  const apiClient = modules.api.createApiClient({
    fetchImpl: options.fetchImpl,
    baseUrl: options.baseUrl || target.location?.origin,
    onDiagnostic: entry => diagnostics.record(entry),
    onSessionExpired: () => {
      replaceServerSlice(store, "session", {
        status: "error",
        reason: "session-expired",
      });
      if (loginRequested) return;
      loginRequested = true;
      if (options.onLoginRequired) options.onLoginRequired("/login");
      else target.location.assign("/login");
    },
  });
  cleanups.push(() => apiClient.cancelAll("runtime-stop"));

  const bootstrapTask = tasks.start({
    owner: "runtime",
    name: "Load current Sonder state",
    phase: "bootstrap",
  });
  const bootstrapResult = await apiClient.get("/api/bootstrap", {
    channel: "runtime-bootstrap",
    owner: "runtime",
  });
  const bootstrap = bootstrapResult.data;
  if (!bootstrap || typeof bootstrap !== "object" || Array.isArray(bootstrap)) {
    throw new modules.errors.ApiError("malformed-response", {
      status: bootstrapResult.status,
      requestId: bootstrapResult.requestId,
      correlationId: bootstrapResult.correlationId,
      technicalDetail: "Bootstrap was not an object.",
    });
  }

  const localizer = modules.localization.createLocalizer(
    modules.localization.projectionFromBootstrap(bootstrap),
  );
  localizer.localize(documentRef);

  const libraryItems = [
    ...(bootstrap.chats || []),
    ...(bootstrap.characters || []),
    ...(bootstrap.personas || []),
    ...(bootstrap.lorebooks || []),
  ];
  replaceServerSlice(store, "session", { status: "ready", actor: "host" });
  replaceServerSlice(store, "library", {
    status: libraryItems.length ? "ready" : "empty",
    chats: bootstrap.chats || [],
    characters: bootstrap.characters || [],
    personas: bootstrap.personas || [],
    lorebooks: bootstrap.lorebooks || [],
  });
  replaceServerSlice(store, "settings", {
    status: "ready",
    data: settingsProjection(bootstrap),
  });
  const extensionBootstrap = extensionBootstrapProjection(bootstrap);

  const router = modules.router.createRouter({
    target,
    explain: key => localizer.t(key),
    onRoute: route => replacePresentationSlice(store, "route", {
      status: "ready",
      ...route,
    }),
  });
  router.start();
  cleanups.push(() => router.stop());

  const registry = modules.extensions.createExtensionRegistry({
    apiClient,
    document: documentRef,
    stateProvider: () => ({
      boot: extensionBootstrap,
      chat: store.getSnapshot().story.data,
      chatId: store.getSnapshot().story.data?.chat?.id || null,
    }),
    onOpenStory: chatId => router.navigate({
      destination: "play",
      query: { chat: String(chatId) },
    }),
    onFault: entry => diagnostics.record({ kind: "extension-fault", ...entry }),
    onRetired: owner => notices.problem({
      owner,
      condition: "extension-retired",
      message: `Extension ${owner} stopped after repeated errors.`,
      error: { kind: "extension", retryable: false },
    }),
  });
  const adapter = modules.extensionsV1.createV1Adapter(registry);
  const uninstallAdapter = modules.extensionsV1.installV1Adapter(adapter);
  cleanups.push(uninstallAdapter);

  const extensionRows = Array.isArray(bootstrap.extensions) ? bootstrap.extensions : [];
  const extensionLoads = await registry.loadEnabled(extensionRows);
  cleanups.push(() => {
    for (const extension of extensionRows) {
      if (extension?.id) registry.unregisterOwner(extension.id);
    }
  });
  replaceServerSlice(store, "extensions", {
    status: "ready",
    items: extensionRows,
    errors: bootstrap.extension_errors || [],
    lanes: bootstrap.extension_lanes || [],
    uiLoads: extensionLoads,
  });

  if (harness.diagnosticsToggle) {
    const onDiagnostics = () => {
      diagnostics.setEnabled(harness.diagnosticsToggle.checked);
      harness.diagnosticsOutput.hidden = !harness.diagnosticsToggle.checked;
      harness.diagnosticsOutput.textContent = harness.diagnosticsToggle.checked
        ? JSON.stringify(diagnostics.snapshot(), null, 2)
        : "";
      replacePresentationSlice(store, "diagnostics", {
        status: "ready",
        enabled: diagnostics.isEnabled(),
        entries: diagnostics.snapshot(),
      });
    };
    harness.diagnosticsToggle.addEventListener("change", onDiagnostics);
    cleanups.push(() => harness.diagnosticsToggle.removeEventListener("change", onDiagnostics));
  }

  tasks.complete(bootstrapTask, { summary: "Runtime ready" });
  setHarnessStatus(
    harness,
    localizer.t("Runtime services ready"),
    `${(bootstrap.chats || []).length} stories · ${extensionRows.length} extensions`,
  );
  return Object.freeze({
    store,
    apiClient,
    localizer,
    tasks,
    notices,
    diagnostics,
    localState,
    router,
    registry,
    adapter,
  });
}

export async function bootRuntime(options = {}) {
  activeTeardown?.();
  activeTeardown = null;

  const target = options.target || window;
  const root = options.root || document.documentElement;
  const modules = await loadRuntimeModules(options.importModule);
  let diagnosticSink = options.onDiagnostic;
  const cleanups = [installErrorBoundary(
    target,
    root,
    entry => diagnosticSink?.(entry),
  )];
  const host = options.host === true || root.dataset.uiNextEntry === "runtime-harness";
  let services = Object.freeze({});

  delete root.dataset.uiNextReady;
  root.dataset.uiNextRelease = MODULE_RELEASE;
  root.dataset.uiNextState = "loading";

  try {
    if (host) {
      services = await startHostRuntime({ modules, target, root, options, cleanups });
      diagnosticSink = entry => {
        options.onDiagnostic?.(entry);
        services.diagnostics.record(entry);
      };
    }
  } catch (error) {
    root.dataset.uiNextState = "failed";
    const harness = harnessElements(options.document || root.ownerDocument || document);
    setHarnessStatus(
      harness,
      "Runtime services unavailable",
      "The replacement runtime could not start. Your saved stories were not changed.",
    );
    for (const cleanup of cleanups.reverse()) cleanup?.();
    throw error;
  }

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

  return { modules, services, teardown: activeTeardown };
}
