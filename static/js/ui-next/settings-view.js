export const MODULE_RELEASE = "wp07.1";

import { appearance } from "../ui/appearance.js?release=wp07.1";
import { initAccessibility, updateAccessibility } from "../ui/accessibility.js?release=wp07.1";

const CATEGORIES = Object.freeze([
  ["experience", "Experience", "theme"],
  ["ai-connections", "AI Connections", "api"],
  ["content", "Content", "prompt"],
  ["add-ons", "Add-ons", "extension"],
  ["maintenance", "Maintenance", "update"],
  ["advanced", "Advanced", "terminal"],
]);

const THEME_COPY = Object.freeze({
  "carbon-signal": ["Carbon Signal", "Carbon, signal cyan, and amber.", ["#071015", "#11252a", "#64dce5", "#c7a85b"]],
  "ash-brass": ["Ash and Brass", "Warm graphite, muted brass, cool blue.", ["#111316", "#22282c", "#7f9eaa", "#b89752"]],
  "midnight-ink": ["Midnight Ink", "Blue-black, violet, and silver-blue.", ["#090d18", "#111b2b", "#68b8c8", "#998bc1"]],
  "parchment-night": ["Parchment Night", "Dark umber, ink, and warm cream.", ["#15100d", "#2a211a", "#819da0", "#c99a58"]],
});

const ACCESSIBILITY = Object.freeze([
  ["mode", "Accessibility Mode", "Enable the recommended visual accessibility adjustments together."],
  ["solidSurfaces", "Solid surfaces", "Remove transparency and blur while preserving the layout."],
  ["highContrast", "High contrast", "Strengthen text and boundaries without replacing the theme."],
  ["reducedMotion", "Reduced motion", "Reduce animation and atmospheric movement."],
  ["strongFocus", "Strong focus", "Make keyboard focus more prominent."],
  ["largeUi", "Large interface", "Increase interface type and control sizing."],
  ["largeProse", "Large story text", "Increase the reading size without changing controls."],
  ["roomyTargets", "Roomy controls", "Increase touch targets and control spacing."],
]);

const ADVANCED_LAUNCHERS = Object.freeze([
  ["prompts", "prompt", "Prompt editor", "Inspect and edit the engine's advanced prompt templates"],
  ["turn-details", "terminal", "Turn details", "Show the live technical stage log while a turn runs"],
  ["story-data", "world", "Raw story data", "Open the current story's internal world record"],
  ["clothing-data", "clothing", "Raw clothing data", "Open the current story's attire and visible-state record"],
]);

function el(documentRef, tag, className = "", text = "") {
  const node = documentRef.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function icon(documentRef, name) {
  const svg = documentRef.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("ui-icon");
  svg.setAttribute("aria-hidden", "true");
  const use = documentRef.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/assets/icons/sonder-icons.svg#icon-${name}`);
  svg.append(use);
  return svg;
}

function categoryNav(documentRef, services, active) {
  const nav = el(documentRef, "nav", "ui-settings__categories");
  nav.dataset.settingsCategories = "true";
  nav.setAttribute("aria-label", "Settings categories");
  CATEGORIES.forEach(([id, label, iconName], index) => {
    const link = el(documentRef, "a", "ui-settings__category");
    link.href = `#/settings/${id}`;
    link.dataset.settingsCategory = id;
    if (id === active) link.setAttribute("aria-current", "page");
    const indexLabel = el(documentRef, "span", "ui-settings__index", String(index + 1).padStart(2, "0"));
    indexLabel.setAttribute("aria-hidden", "true");
    link.append(
      indexLabel,
      icon(documentRef, iconName),
      el(documentRef, "span", "ui-settings__category-label", services.localizer.t(label)),
    );
    link.addEventListener("click", event => {
      event.preventDefault();
      services.router.navigate({ destination: "settings", segments: [id] });
    });
    nav.append(link);
  });
  return nav;
}

function themeChoice(documentRef, services, id, active) {
  const [name, detail, colors] = THEME_COPY[id];
  const control = el(documentRef, "button", "ui-settings__theme-choice");
  control.type = "button";
  control.dataset.themeChoice = id;
  control.setAttribute("aria-label", `Use ${name} theme`);
  const swatches = el(documentRef, "span", "ui-settings__swatches");
  colors.forEach(color => {
    const swatch = el(documentRef, "span");
    swatch.style.backgroundColor = color;
    swatches.append(swatch);
  });
  const copy = el(documentRef, "span", "ui-settings__theme-copy");
  copy.append(el(documentRef, "strong", "", name), el(documentRef, "small", "", detail), swatches);
  const status = el(documentRef, "span", "ui-settings__theme-status", id === active ? "Selected" : "Use");
  control.append(el(documentRef, "span", "ui-settings__index", String(Object.keys(THEME_COPY).indexOf(id) + 1).padStart(2, "0")), copy, status);
  control.addEventListener("click", () => {
    appearance.setTheme(id);
    const stored = services.localState.snapshot().appearance || {};
    services.localState.setRecord("appearance", { ...stored, theme: id });
    control.closest(".ui-settings__group")?.querySelector(".ui-settings__theme-readout")?.replaceChildren(name);
    for (const candidate of control.parentElement.children) {
      const selected = candidate.dataset.themeChoice === id;
      candidate.setAttribute("aria-pressed", String(selected));
      candidate.querySelector(".ui-settings__theme-status").textContent = selected ? "Selected" : "Use";
    }
  });
  control.setAttribute("aria-pressed", String(id === active));
  return control;
}

function toggleRow(documentRef, key, label, detail, preferences, onUpdate) {
  const row = el(documentRef, "label", "ui-settings__toggle-row");
  const copy = el(documentRef, "span", "ui-settings__field-copy");
  copy.append(el(documentRef, "strong", "", label), el(documentRef, "small", "", detail));
  const input = documentRef.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(preferences[key]);
  input.dataset.accessibilityKey = key;
  input.setAttribute("aria-label", label);
  const visual = el(documentRef, "span", "ui-settings__toggle-visual");
  const state = el(documentRef, "span", "ui-settings__toggle-state", input.checked ? "On" : "Off");
  input.addEventListener("change", () => {
    const next = updateAccessibility({ [key]: input.checked });
    onUpdate?.(next);
  });
  row.append(copy, input, visual, state);
  return row;
}

function experience(documentRef, services) {
  const section = el(documentRef, "section", "ui-settings__section");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", "Settings / 01"),
    el(documentRef, "h2", "ui-heading ui-heading--2", "Experience"),
    el(documentRef, "p", "ui-muted", "Look, reading, sound, motion, and accessibility"),
  );
  const themeGroup = el(documentRef, "section", "ui-settings__group");
  const themeHead = el(documentRef, "div", "ui-settings__field-head");
  const copy = el(documentRef, "span", "ui-settings__field-copy");
  copy.append(el(documentRef, "strong", "", "Theme"), el(documentRef, "small", "", "Four restrained, genre-neutral palettes. Theme changes stay on this device."));
  themeHead.append(copy, el(documentRef, "code", "ui-settings__theme-readout", THEME_COPY[documentRef.documentElement.dataset.theme]?.[0] || "Carbon Signal"));
  const themes = el(documentRef, "div", "ui-settings__theme-ledger");
  const active = documentRef.documentElement.dataset.theme || "carbon-signal";
  Object.keys(THEME_COPY).forEach(id => themes.append(themeChoice(documentRef, services, id, active)));
  const legacy = el(documentRef, "div", "ui-settings__legacy");
  const legacyCopy = el(documentRef, "span", "ui-settings__field-copy");
  legacyCopy.append(el(documentRef, "strong", "", "Legacy themes"), el(documentRef, "small", "", "Kept for compatibility."));
  const select = documentRef.createElement("select");
  select.setAttribute("aria-label", "Legacy themes");
  select.append(el(documentRef, "option", "", "Choose a legacy theme"));
  legacy.append(legacyCopy, select);
  themeGroup.append(themeHead, themes, legacy);

  const accessibilityGroup = el(documentRef, "section", "ui-settings__group");
  const preferences = initAccessibility();
  const syncAccessibility = next => {
    accessibilityGroup.querySelectorAll("input[data-accessibility-key]").forEach(input => {
      const enabled = Boolean(next[input.dataset.accessibilityKey]);
      input.checked = enabled;
      input.closest(".ui-settings__toggle-row").querySelector(".ui-settings__toggle-state").textContent = enabled ? "On" : "Off";
    });
  };
  ACCESSIBILITY.forEach(([key, label, detail]) => accessibilityGroup.append(
    toggleRow(documentRef, key, label, detail, preferences, syncAccessibility),
  ));
  section.append(head, themeGroup, accessibilityGroup);
  return section;
}

function placeholder(documentRef, active) {
  const definition = CATEGORIES.find(([id]) => id === active) || CATEGORIES[0];
  const section = el(documentRef, "section", "ui-settings__section");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", `Settings / ${String(CATEGORIES.indexOf(definition) + 1).padStart(2, "0")}`),
    el(documentRef, "h2", "ui-heading ui-heading--2", definition[1]),
  );
  section.append(head, el(documentRef, "p", "ui-muted", "This category will be connected to its current engine controls in the next Settings slice."));
  return section;
}

function advanced(documentRef) {
  const section = el(documentRef, "section", "ui-settings__section ui-settings__section--advanced");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", "Settings / 06"),
    el(documentRef, "h2", "ui-heading ui-heading--2", "Advanced"),
    el(documentRef, "p", "ui-muted", "Prompts, diagnostics, and raw story data"),
  );
  const launchers = el(documentRef, "section", "ui-settings__group ui-settings__launcher-group");
  ADVANCED_LAUNCHERS.forEach(([id, iconName, label, detail]) => {
    const control = el(documentRef, "button", "ui-settings__launcher");
    control.type = "button";
    control.dataset.settingsLauncher = id;
    const copy = el(documentRef, "span", "ui-settings__launcher-copy");
    copy.append(el(documentRef, "strong", "", label), el(documentRef, "small", "", detail));
    control.append(icon(documentRef, iconName), copy, icon(documentRef, "chevron-right"));
    launchers.append(control);
  });
  const warning = el(documentRef, "aside", "ui-settings__warning");
  const warningCopy = el(documentRef, "span", "ui-settings__launcher-copy");
  warningCopy.append(
    el(documentRef, "strong", "", "Advanced tools change engine-facing data."),
    el(documentRef, "small", "", "Use them when correcting a known problem or diagnosing a turn."),
  );
  warning.append(icon(documentRef, "warning"), warningCopy);
  section.append(head, launchers, warning);
  return section;
}

function aiConnections(documentRef, services, state) {
  const data = state.settings?.data || {};
  const providers = Array.isArray(data.providers) ? data.providers : [];
  const defaultModel = data.agent_models?.default || {};
  const section = el(documentRef, "section", "ui-settings__section ui-settings__section--ai");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", "Settings / 02"),
    el(documentRef, "h2", "ui-heading ui-heading--2", "AI Connections"),
    el(documentRef, "p", "ui-muted", "Providers, credentials, models, and generation defaults"),
  );

  const connections = el(documentRef, "section", "ui-settings__group ui-settings__provider-group");
  const connectionsHead = el(documentRef, "div", "ui-settings__field-head");
  const connectionsCopy = el(documentRef, "span", "ui-settings__field-copy");
  connectionsCopy.append(
    el(documentRef, "strong", "", "Connections"),
    el(documentRef, "small", "", "Sonder only shows whether a credential is stored. Secret values are never read back."),
  );
  const connectionActions = el(documentRef, "span", "ui-settings__connection-actions");
  const addProvider = el(documentRef, "button", "ui-button ui-button--quiet", "Add provider");
  addProvider.type = "button";
  connectionActions.append(
    el(documentRef, "code", "ui-settings__theme-readout", `${providers.length} connected`),
    addProvider,
  );
  connectionsHead.append(connectionsCopy, connectionActions);
  connections.append(connectionsHead);

  const setup = el(documentRef, "form", "ui-settings__connection-form");
  setup.hidden = true;
  setup.setAttribute("aria-label", "Add AI provider");
  const setupFields = el(documentRef, "div", "ui-settings__connection-fields");
  const kindField = el(documentRef, "label", "ui-field");
  kindField.append(el(documentRef, "span", "ui-field__label", "Provider"));
  const kind = documentRef.createElement("select");
  kind.setAttribute("aria-label", "Provider");
  const presets = data.provider_presets && typeof data.provider_presets === "object"
    ? data.provider_presets : {};
  Object.keys(presets).sort().forEach(id => {
    const label = id.charAt(0).toUpperCase() + id.slice(1);
    const option = el(documentRef, "option", "", label);
    option.value = id;
    kind.append(option);
  });
  kindField.append(kind);
  const nameField = el(documentRef, "label", "ui-field");
  nameField.append(el(documentRef, "span", "ui-field__label", "Connection name"));
  const name = documentRef.createElement("input");
  name.type = "text";
  name.setAttribute("aria-label", "Connection name");
  nameField.append(name);
  const endpointField = el(documentRef, "label", "ui-field");
  endpointField.append(el(documentRef, "span", "ui-field__label", "Endpoint"));
  const endpoint = documentRef.createElement("input");
  endpoint.type = "url";
  endpoint.setAttribute("aria-label", "Endpoint");
  endpointField.append(endpoint);
  const keyField = el(documentRef, "label", "ui-field");
  keyField.append(el(documentRef, "span", "ui-field__label", "API key"));
  const apiKey = documentRef.createElement("input");
  apiKey.type = "password";
  apiKey.autocomplete = "new-password";
  apiKey.setAttribute("aria-label", "API key");
  keyField.append(apiKey);
  setupFields.append(kindField, nameField, endpointField, keyField);
  const setupStatus = el(documentRef, "p", "ui-settings__connection-status");
  setupStatus.setAttribute("role", "status");
  const setupActions = el(documentRef, "div", "ui-settings__connection-footer");
  const cancelSetup = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
  cancelSetup.type = "button";
  const connect = el(documentRef, "button", "ui-button ui-button--primary", "Connect and test");
  connect.type = "submit";
  setupActions.append(cancelSetup, connect);
  const modelStage = el(documentRef, "div", "ui-settings__model-stage");
  modelStage.hidden = true;
  const modelField = el(documentRef, "label", "ui-field");
  modelField.append(el(documentRef, "span", "ui-field__label", "Default model"));
  const modelSelect = documentRef.createElement("select");
  modelSelect.setAttribute("aria-label", "Default model");
  modelField.append(modelSelect);
  const saveDefault = el(documentRef, "button", "ui-button ui-button--primary", "Save default model");
  saveDefault.type = "button";
  modelStage.append(modelField, saveDefault);
  setup.append(setupFields, setupStatus, setupActions, modelStage);
  connections.append(setup);

  const syncPreset = () => {
    const id = kind.value;
    name.value = id ? id.charAt(0).toUpperCase() + id.slice(1) : "";
    endpoint.value = presets[id] || "";
  };
  kind.addEventListener("change", syncPreset);
  syncPreset();
  let providerEmpty = null;
  let editingProvider = null;
  let createdProvider = null;
  const openProviderForm = (provider = null) => {
    editingProvider = provider;
    createdProvider = provider;
    if (provider) {
      kind.value = provider.kind || "generic";
      name.value = provider.name || provider.kind || "";
      endpoint.value = provider.base_url || "";
      apiKey.value = "";
      apiKey.placeholder = provider.has_key ? "Leave blank to keep saved key" : "";
      connect.textContent = "Save and test";
      setup.setAttribute("aria-label", `Edit ${provider.name || provider.kind || "AI"} provider`);
    } else {
      syncPreset();
      apiKey.value = "";
      apiKey.placeholder = "";
      connect.textContent = "Connect and test";
      setup.setAttribute("aria-label", "Add AI provider");
    }
    setup.hidden = false;
    if (providerEmpty) providerEmpty.hidden = true;
    defaults.hidden = true;
    addProvider.setAttribute("aria-expanded", "true");
    kind.focus();
  };
  addProvider.addEventListener("click", () => openProviderForm());
  cancelSetup.addEventListener("click", () => {
    setup.hidden = true;
    if (providerEmpty) providerEmpty.hidden = false;
    defaults.hidden = false;
    addProvider.setAttribute("aria-expanded", "false");
    setupStatus.textContent = "";
    modelStage.hidden = true;
    editingProvider = null;
    createdProvider = null;
    addProvider.focus();
  });

  setup.addEventListener("submit", async event => {
    event.preventDefault();
    connect.disabled = true;
    setupStatus.textContent = "Saving the connection and checking its model list…";
    try {
      const payload = {
        name: name.value.trim(),
        kind: kind.value,
        base_url: endpoint.value.trim(),
        api_key: apiKey.value,
      };
      const saved = editingProvider
        ? await services.apiClient.put(`/api/providers/${editingProvider.id}`, payload, {
            channel: `settings-provider-save:${editingProvider.id}`,
            owner: `settings-provider:${editingProvider.id}`,
          })
        : await services.apiClient.post("/api/providers", payload, {
            channel: "settings-provider-create",
            owner: "settings-provider:new",
          });
      createdProvider = saved.data;
      const result = await services.apiClient.get(`/api/providers/${createdProvider.id}/models`, {
        channel: `settings-provider-test:${createdProvider.id}`,
        owner: `settings-provider:${createdProvider.id}`,
      });
      if (!connect.isConnected) return;
      const models = (Array.isArray(result.data?.models) ? result.data.models : [])
        .map(item => typeof item === "string" ? item : item?.id || item?.name)
        .filter(Boolean);
      modelSelect.replaceChildren();
      models.forEach(id => {
        const option = el(documentRef, "option", "", id);
        option.value = id;
        modelSelect.append(option);
      });
      setupStatus.textContent = models.length
        ? `Connection works. ${models.length} ${models.length === 1 ? "model" : "models"} available.`
        : "Connection works, but this provider returned no models.";
      modelStage.hidden = !models.length;
      if (models.length) modelSelect.focus();
    } catch (error) {
      if (!connect.isConnected) return;
      setupStatus.textContent = error?.userMessage || error?.message || "Sonder could not connect to this provider.";
    } finally {
      if (connect.isConnected) connect.disabled = false;
    }
  });
  saveDefault.addEventListener("click", async () => {
    if (!createdProvider || !modelSelect.value) return;
    saveDefault.disabled = true;
    const agentModels = {
      ...(data.agent_models || {}),
      default: { provider: createdProvider.id, model: modelSelect.value },
    };
    try {
      await services.apiClient.put("/api/agent_models", agentModels, {
        channel: "settings-agent-models-save",
        owner: "settings-agent-models",
      });
      services.store.dispatch({
        type: "server/replace",
        slice: "settings",
        value: {
          ...state.settings,
          data: {
            ...data,
            providers: providers.some(provider => provider.id === createdProvider.id)
              ? providers.map(provider => provider.id === createdProvider.id ? createdProvider : provider)
              : [...providers, createdProvider],
            agent_models: agentModels,
          },
        },
      });
    } catch (error) {
      if (!saveDefault.isConnected) return;
      setupStatus.textContent = error?.userMessage || error?.message || "Sonder could not save the default model.";
      saveDefault.disabled = false;
    }
  });

  if (!providers.length) {
    providerEmpty = el(documentRef, "p", "ui-settings__provider-empty", "No AI provider is connected.");
    connections.append(providerEmpty);
  }
  providers.forEach(provider => {
    const row = el(documentRef, "div", "ui-settings__provider-row");
    const copy = el(documentRef, "span", "ui-settings__launcher-copy");
    const detail = [provider.kind, provider.base_url].filter(Boolean).join(" · ");
    copy.append(
      el(documentRef, "strong", "", provider.name || provider.kind || "Provider"),
      el(documentRef, "small", "", detail),
    );
    const credential = el(
      documentRef,
      "span",
      "ui-settings__provider-credential",
      provider.has_key ? "Key saved" : "No key",
    );
    const test = el(documentRef, "button", "ui-button ui-button--quiet", "Test");
    test.type = "button";
    test.setAttribute("aria-label", `Test ${provider.name || provider.kind || "provider"} connection`);
    const edit = el(documentRef, "button", "ui-button ui-button--quiet", "Edit");
    edit.type = "button";
    edit.setAttribute("aria-label", `Edit ${provider.name || provider.kind || "provider"} connection`);
    edit.addEventListener("click", () => openProviderForm(provider));
    const status = el(documentRef, "p", "ui-settings__provider-status");
    status.setAttribute("role", "status");
    test.addEventListener("click", async () => {
      test.disabled = true;
      status.textContent = "Testing connection…";
      try {
        const result = await services.apiClient.get(`/api/providers/${provider.id}/models`, {
          channel: `settings-provider-test:${provider.id}`,
          owner: `settings-provider:${provider.id}`,
        });
        if (!test.isConnected) return;
        const models = Array.isArray(result.data?.models) ? result.data.models : [];
        status.textContent = `Connection works. ${models.length} ${models.length === 1 ? "model" : "models"} available.`;
      } catch (error) {
        if (!test.isConnected) return;
        status.textContent = error?.userMessage || error?.message || "Sonder could not reach this provider.";
      } finally {
        if (test.isConnected) test.disabled = false;
      }
    });
    row.append(icon(documentRef, "api"), copy, credential, edit, test, status);
    connections.append(row);
  });

  const defaults = el(documentRef, "section", "ui-settings__group");
  const defaultRow = el(documentRef, "div", "ui-settings__field-head");
  const defaultCopy = el(documentRef, "span", "ui-settings__field-copy");
  defaultCopy.append(
    el(documentRef, "strong", "", "Default model"),
    el(documentRef, "small", "", "Used when a specialized engine role does not name its own model."),
  );
  defaultRow.append(
    defaultCopy,
    el(documentRef, "code", "ui-settings__theme-readout", defaultModel.model || "Not selected"),
  );
  defaults.append(defaultRow);
  section.append(head, connections, defaults);
  return section;
}

export function createSettingsView(options = {}) {
  const documentRef = options.document || document;
  const { services, state } = options;
  const route = state.route || services.router.current();
  const requested = route.segments?.[0] || "experience";
  const active = CATEGORIES.some(([id]) => id === requested) ? requested : "experience";
  const root = el(documentRef, "section", "ui-settings");
  root.dataset.settingsShell = "true";
  const header = el(documentRef, "header", "ui-settings__header");
  const title = el(documentRef, "div");
  title.append(el(documentRef, "p", "ui-settings__kicker", "Settings"), el(documentRef, "h1", "ui-heading ui-heading--1", "Sonder preferences"));
  const search = documentRef.createElement("input");
  search.type = "search";
  search.placeholder = "Search settings";
  search.setAttribute("aria-label", "Search settings");
  const searchField = el(documentRef, "label", "ui-settings__search");
  searchField.append(icon(documentRef, "search"), search);
  header.append(title, searchField);
  const body = el(documentRef, "div", "ui-settings__body");
  const nav = categoryNav(documentRef, services, active);
  const content = el(documentRef, "main", "ui-settings__content");
  content.dataset.settingsContent = "true";
  content.append(
    active === "experience"
      ? experience(documentRef, services)
      : active === "ai-connections"
        ? aiConnections(documentRef, services, state)
      : active === "advanced"
        ? advanced(documentRef)
        : placeholder(documentRef, active),
  );
  body.append(nav, content);
  root.append(header, body);
  services.localizer.localize(root);
  requestAnimationFrame(() => nav.querySelector("[aria-current='page']")?.scrollIntoView({ block: "nearest", inline: "center" }));
  return { element: root, teardown() {} };
}
