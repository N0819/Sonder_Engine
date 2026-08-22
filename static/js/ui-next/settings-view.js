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

function humanizeSettingKey(value) {
  return String(value || "")
    .replace(/^ext:/, "")
    .replace(/[_:-]+/g, " ")
    .replace(/\b\w/g, letter => letter.toUpperCase());
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

function settingToggle(documentRef, label, detail, checked) {
  const row = el(documentRef, "label", "ui-settings__toggle-row");
  const copy = el(documentRef, "span", "ui-settings__field-copy");
  copy.append(el(documentRef, "strong", "", label), el(documentRef, "small", "", detail));
  const input = documentRef.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(checked);
  input.setAttribute("aria-label", label);
  const visual = el(documentRef, "span", "ui-settings__toggle-visual");
  const state = el(documentRef, "span", "ui-settings__toggle-state", input.checked ? "On" : "Off");
  input.addEventListener("change", () => {
    state.textContent = input.checked ? "On" : "Off";
  });
  row.append(copy, input, visual, state);
  return { row, input };
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

function contentSettings(documentRef, services, state) {
  const data = state.settings?.data || {};
  const section = el(documentRef, "section", "ui-settings__section");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", "Settings / 03"),
    el(documentRef, "h2", "ui-heading ui-heading--2", "Content"),
    el(documentRef, "p", "ui-muted", "Story boundaries, authored detail, and local data"),
  );

  const permissions = el(documentRef, "section", "ui-settings__group");
  const adult = settingToggle(
    documentRef,
    "Allow adult story content",
    "Lets stories use mature material. This does not change provider policies or add content by itself.",
    data.nsfw_enabled,
  );
  const beneath = settingToggle(
    documentRef,
    "Use underneath descriptions from cards",
    "Includes author-written body-region detail when clothing no longer covers it. Card text is not erased when this is off.",
    data.attire_beneath,
  );
  const promote = settingToggle(
    documentRef,
    "Allow stories to promote recurring extras",
    "Permits a story to turn a recurring extra into a full cast member after its own story-level threshold is met.",
    data.auto_promote,
  );
  permissions.append(adult.row, beneath.row, promote.row);
  const actions = el(documentRef, "div", "ui-settings__connection-footer");
  const status = el(documentRef, "p", "ui-settings__connection-status");
  status.setAttribute("role", "status");
  const save = el(documentRef, "button", "ui-button ui-button--primary", "Save content preferences");
  save.type = "button";
  actions.append(save);
  save.addEventListener("click", async () => {
    save.disabled = true;
    status.textContent = "Saving content preferences…";
    try {
      await services.apiClient.put("/api/nsfw", { enabled: adult.input.checked }, {
        channel: "settings-content-nsfw", owner: "settings-content",
      });
      await services.apiClient.put("/api/attire_beneath", { enabled: beneath.input.checked }, {
        channel: "settings-content-attire", owner: "settings-content",
      });
      await services.apiClient.put("/api/auto_promote", { enabled: promote.input.checked }, {
        channel: "settings-content-promotion", owner: "settings-content",
      });
      if (save.isConnected) status.textContent = "Content preferences saved.";
    } catch (error) {
      if (save.isConnected) status.textContent = error?.userMessage || error?.message || "Sonder could not save content preferences.";
    } finally {
      if (save.isConnected) save.disabled = false;
    }
  });
  permissions.append(status, actions);

  const localData = el(documentRef, "section", "ui-settings__group ui-settings__data-note");
  const dataCopy = el(documentRef, "span", "ui-settings__field-copy");
  dataCopy.append(
    el(documentRef, "strong", "", "Your stories stay on this Sonder host."),
    el(documentRef, "small", "", "Story exports and permanent deletion remain attached to the specific story or Library item, so a broad control cannot erase the wrong data."),
  );
  const manage = el(documentRef, "a", "ui-button ui-button--quiet", "Manage story exports and deletion");
  manage.href = "#/library/stories";
  localData.append(dataCopy, manage);
  section.append(head, permissions, localData);
  return section;
}

function extensionTrustText(extension) {
  const trust = String(extension?.trust || "code");
  if (trust === "data") return "Data only. It runs no code.";
  if (trust === "prompt") return "Supplies prompt text. It runs no code of its own.";
  return "Runs code inside Sonder with access to stories, world state, and provider connections.";
}

function addOnsSettings(documentRef, services) {
  const section = el(documentRef, "section", "ui-settings__section");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", "Settings / 04"),
    el(documentRef, "h2", "ui-heading ui-heading--2", "Add-ons"),
    el(documentRef, "p", "ui-muted", "Installed extensions, permissions, updates, and settings"),
  );
  const status = el(documentRef, "p", "ui-settings__connection-status", "Loading installed extensions…");
  status.setAttribute("role", "status");
  const list = el(documentRef, "section", "ui-settings__group ui-settings__extension-list");
  const install = el(documentRef, "section", "ui-settings__group");
  const installCopy = el(documentRef, "span", "ui-settings__field-copy");
  installCopy.append(
    el(documentRef, "strong", "", "Install an extension"),
    el(documentRef, "small", "", "Use a git repository, a zip URL, or a local folder. New extensions arrive switched off."),
  );
  const installControls = el(documentRef, "div", "ui-settings__install-row");
  const source = documentRef.createElement("input");
  source.type = "text";
  source.placeholder = "Repository, zip URL, or local folder";
  source.setAttribute("aria-label", "Extension source");
  const stageInstall = el(documentRef, "button", "ui-button ui-button--quiet", "Install extension");
  stageInstall.type = "button";
  installControls.append(source, stageInstall);
  const installConsent = el(documentRef, "div", "ui-settings__extension-consent");
  installConsent.hidden = true;
  const installWarning = el(documentRef, "p", "", "Nothing has reviewed this code. Installation copies it to this Sonder host; it still will not run until you enable it.");
  const confirmInstall = el(documentRef, "button", "ui-button ui-button--primary", "Confirm install extension");
  confirmInstall.type = "button";
  const cancelInstall = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel installation");
  cancelInstall.type = "button";
  installConsent.append(installWarning, confirmInstall, cancelInstall);
  install.append(installCopy, installControls, installConsent);

  let listing = null;
  let updateReports = new Map();
  const render = () => {
    list.replaceChildren();
    if (!listing) return;
    if (listing.safe_mode) {
      const safeMode = el(documentRef, "aside", "ui-settings__warning");
      const copy = el(documentRef, "span", "ui-settings__launcher-copy");
      copy.append(
        el(documentRef, "strong", "", "Safe mode is active."),
        el(documentRef, "small", "", "Every extension is off for this run. Restart without safe mode to load enabled extensions."),
      );
      safeMode.append(icon(documentRef, "warning"), copy);
      list.append(safeMode);
    }
    for (const failure of listing.load_errors || []) {
      const error = el(documentRef, "div", "ui-settings__extension-error");
      error.append(
        el(documentRef, "strong", "", `${failure.dir || "An extension"} failed to load`),
        el(documentRef, "small", "", String(failure.error || failure)),
      );
      list.append(error);
    }
    const extensions = Array.isArray(listing.extensions) ? listing.extensions : [];
    list.dataset.extensionCount = String(extensions.length);
    if (!extensions.length) list.append(el(documentRef, "p", "ui-settings__provider-empty", "No extensions are installed."));
    extensions.forEach(extension => {
      const name = extension.name || extension.id;
      const row = el(documentRef, "article", "ui-settings__extension-row");
      const rowHead = el(documentRef, "div", "ui-settings__extension-head");
      const title = el(documentRef, "span", "ui-settings__field-copy");
      title.append(
        el(documentRef, "strong", "", name),
        el(documentRef, "small", "", `v${extension.version || "?"} · ${extension.provenance || "local"}`),
      );
      const enabled = el(documentRef, "span", "ui-settings__provider-credential", extension.enabled ? "Enabled" : "Disabled");
      rowHead.append(title, enabled);
      if (extension.description) row.append(rowHead, el(documentRef, "p", "ui-muted", extension.description));
      else row.append(rowHead);
      const permissions = Array.isArray(extension.disclosures) ? extension.disclosures : [];
      if (permissions.length) {
        const permissionList = el(documentRef, "ul", "ui-settings__permission-list");
        permissions.forEach(permission => permissionList.append(el(documentRef, "li", "", permission)));
        row.append(permissionList);
      }
      row.append(el(documentRef, "p", "ui-settings__trust-note", extensionTrustText(extension)));
      if (extension.error) row.append(el(documentRef, "p", "ui-settings__extension-error", String(extension.error)));
      const actions = el(documentRef, "div", "ui-settings__extension-actions");
      const toggle = el(documentRef, "button", "ui-button ui-button--quiet", extension.enabled ? `Disable ${name}` : `Enable ${name}`);
      toggle.type = "button";
      const remove = el(documentRef, "button", "ui-button ui-button--quiet", `Remove ${name}`);
      remove.type = "button";
      const report = updateReports.get(extension.id);
      if (report?.update) {
        const update = el(documentRef, "button", "ui-button ui-button--primary", `Update ${name}`);
        update.type = "button";
        update.addEventListener("click", async () => {
          update.disabled = true;
          status.textContent = `Updating ${name}…`;
          try {
            await services.apiClient.post(`/api/extensions/${encodeURIComponent(extension.id)}/update`, {}, {
              channel: `settings-extension-update:${extension.id}`, owner: "settings-add-ons",
            });
            services.registry.unregisterOwner(extension.id);
            updateReports.delete(extension.id);
            await load();
          } catch (error) {
            status.textContent = error?.userMessage || error?.message || `Sonder could not update ${name}.`;
          }
        });
        actions.append(update);
      }
      actions.append(toggle, remove);
      row.append(actions);
      const consent = el(documentRef, "div", "ui-settings__extension-consent");
      consent.hidden = true;
      row.append(consent);
      toggle.addEventListener("click", async () => {
        if (extension.enabled) {
          toggle.disabled = true;
          status.textContent = `Disabling ${name}…`;
          try {
            await services.apiClient.post(`/api/extensions/${encodeURIComponent(extension.id)}/disable`, {}, {
              channel: `settings-extension-toggle:${extension.id}`, owner: "settings-add-ons",
            });
            services.registry.unregisterOwner(extension.id);
            await load();
          } catch (error) {
            status.textContent = error?.userMessage || error?.message || `Sonder could not disable ${name}.`;
          }
          return;
        }
        consent.replaceChildren(
          el(documentRef, "strong", "", "Nothing has reviewed this code."),
          el(documentRef, "p", "", extensionTrustText(extension)),
        );
        if (permissions.length) {
          const disclosure = el(documentRef, "ul", "ui-settings__permission-list");
          permissions.forEach(permission => disclosure.append(el(documentRef, "li", "", permission)));
          consent.append(disclosure);
        }
        const confirm = el(documentRef, "button", "ui-button ui-button--primary", `Confirm enable ${name}`);
        confirm.type = "button";
        const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
        cancel.type = "button";
        consent.append(confirm, cancel);
        consent.hidden = false;
        confirm.addEventListener("click", async () => {
          confirm.disabled = true;
          status.textContent = `Enabling ${name}…`;
          try {
            await services.apiClient.post(`/api/extensions/${encodeURIComponent(extension.id)}/enable`, {}, {
              channel: `settings-extension-toggle:${extension.id}`, owner: "settings-add-ons",
            });
            await services.registry.loadEnabled([{ ...extension, enabled: true }]);
            await load();
          } catch (error) {
            status.textContent = error?.userMessage || error?.message || `Sonder could not enable ${name}.`;
          }
        });
        cancel.addEventListener("click", () => {
          consent.hidden = true;
          toggle.focus();
        });
      });
      remove.addEventListener("click", () => {
        consent.replaceChildren(
          el(documentRef, "strong", "", `Remove ${name}?`),
          el(documentRef, "p", "", "Its files will be deleted. Story data it owns is kept so reinstalling can recover it."),
        );
        const confirm = el(documentRef, "button", "ui-button ui-button--danger", `Confirm remove ${name}`);
        confirm.type = "button";
        const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
        cancel.type = "button";
        consent.append(confirm, cancel);
        consent.hidden = false;
        confirm.addEventListener("click", async () => {
          confirm.disabled = true;
          status.textContent = `Removing ${name}…`;
          try {
            await services.apiClient.delete(`/api/extensions/${encodeURIComponent(extension.id)}`, {
              channel: `settings-extension-remove:${extension.id}`, owner: "settings-add-ons",
            });
            services.registry.unregisterOwner(extension.id);
            await load();
          } catch (error) {
            status.textContent = error?.userMessage || error?.message || `Sonder could not remove ${name}.`;
          }
        });
        cancel.addEventListener("click", () => {
          consent.hidden = true;
          remove.focus();
        });
      });
      list.append(row);
    });
    const footer = el(documentRef, "div", "ui-settings__extension-footer");
    footer.append(el(documentRef, "small", "ui-muted", `Extension API ${listing.ext_api || "?"}`));
    const checkUpdates = el(documentRef, "button", "ui-button ui-button--quiet", "Check for extension updates");
    checkUpdates.type = "button";
    checkUpdates.addEventListener("click", async () => {
      checkUpdates.disabled = true;
      status.textContent = "Checking extension updates…";
      try {
        const result = await services.apiClient.get("/api/extensions/updates", {
          channel: "settings-extension-updates", owner: "settings-add-ons",
        });
        updateReports = new Map((result.data?.updates || []).map(report => [report.id, report]));
        status.textContent = "Extension update check finished.";
        render();
      } catch (error) {
        status.textContent = error?.userMessage || error?.message || "Sonder could not check extension updates.";
      }
    });
    footer.append(checkUpdates);
    list.append(footer);
  };
  const load = async () => {
    try {
      const result = await services.apiClient.get("/api/extensions", {
        channel: "settings-extensions-list", owner: "settings-add-ons",
      });
      if (!section.isConnected) return;
      listing = result.data || {};
      status.textContent = "";
      render();
    } catch (error) {
      if (!section.isConnected) return;
      status.textContent = error?.userMessage || error?.message || "Sonder could not load installed extensions.";
    }
  };
  stageInstall.addEventListener("click", () => {
    if (!source.value.trim()) {
      status.textContent = "Enter a repository, zip URL, or local folder first.";
      source.focus();
      return;
    }
    installConsent.hidden = false;
    confirmInstall.focus();
  });
  cancelInstall.addEventListener("click", () => {
    installConsent.hidden = true;
    stageInstall.focus();
  });
  confirmInstall.addEventListener("click", async () => {
    confirmInstall.disabled = true;
    status.textContent = "Installing extension…";
    try {
      await services.apiClient.post("/api/extensions/install", { source: source.value.trim() }, {
        channel: "settings-extension-install", owner: "settings-add-ons",
      });
      source.value = "";
      installConsent.hidden = true;
      await load();
    } catch (error) {
      status.textContent = error?.userMessage || error?.message || "Sonder could not install the extension.";
    } finally {
      if (confirmInstall.isConnected) confirmInstall.disabled = false;
    }
  });
  section.append(head, status, list, install);
  queueMicrotask(load);
  return section;
}

function maintenanceSettings(documentRef, services) {
  const section = el(documentRef, "section", "ui-settings__section");
  const head = el(documentRef, "header", "ui-settings__section-head");
  head.append(
    el(documentRef, "p", "ui-settings__crumb", "Settings / 05"),
    el(documentRef, "h2", "ui-heading ui-heading--2", "Maintenance"),
    el(documentRef, "p", "ui-muted", "Updates, storage conversion, and recovery tools"),
  );

  const updates = el(documentRef, "section", "ui-settings__group");
  const updateHead = el(documentRef, "div", "ui-settings__field-head");
  const updateCopy = el(documentRef, "span", "ui-settings__field-copy");
  updateCopy.append(
    el(documentRef, "strong", "", "Sonder updates"),
    el(documentRef, "small", "", "Check the configured Git remote. Nothing downloads or changes until you choose Install update."),
  );
  const checkUpdates = el(documentRef, "button", "ui-button ui-button--quiet", "Check for Sonder updates");
  checkUpdates.type = "button";
  updateHead.append(updateCopy, checkUpdates);
  const updateResult = el(documentRef, "div", "ui-settings__maintenance-result");
  const updateStatus = el(documentRef, "p", "ui-settings__connection-status");
  updateStatus.setAttribute("role", "status");
  updates.append(updateHead, updateResult, updateStatus);
  checkUpdates.addEventListener("click", async () => {
    checkUpdates.disabled = true;
    updateStatus.textContent = "Checking for Sonder updates…";
    updateResult.replaceChildren();
    try {
      const result = await services.apiClient.get("/api/updates/check", {
        channel: "settings-update-check", owner: "settings-maintenance",
      });
      if (!checkUpdates.isConnected) return;
      const report = result.data || {};
      if (!report.ok) throw new Error(report.error || "Update check failed.");
      updateStatus.textContent = `Branch ${report.branch || "unknown"} · current ${report.current || "unknown"}`;
      if (report.up_to_date) {
        updateResult.append(el(documentRef, "strong", "", "Sonder is up to date."));
        return;
      }
      const count = Number(report.behind || 0);
      updateResult.append(el(documentRef, "strong", "", `${count.toLocaleString("en-US")} ${count === 1 ? "update is" : "updates are"} available.`));
      const commits = Array.isArray(report.commits) ? report.commits : [];
      if (commits.length) {
        const changes = el(documentRef, "ul", "ui-settings__permission-list");
        commits.forEach(commit => changes.append(el(documentRef, "li", "", `${commit.hash || ""} ${commit.subject || ""}`.trim())));
        updateResult.append(changes);
      }
      if (report.dirty) {
        updateResult.append(el(documentRef, "p", "ui-settings__warning-inline", "Local uncommitted changes must be committed or stashed before installing."));
        return;
      }
      const installUpdate = el(documentRef, "button", "ui-button ui-button--primary", "Install update");
      installUpdate.type = "button";
      const consent = el(documentRef, "div", "ui-settings__extension-consent");
      consent.hidden = true;
      installUpdate.addEventListener("click", () => {
        consent.replaceChildren(
          el(documentRef, "strong", "", "Install this Sonder update?"),
          el(documentRef, "p", "", "The running server will need a restart."),
        );
        const confirm = el(documentRef, "button", "ui-button ui-button--primary", "Confirm install update");
        confirm.type = "button";
        const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
        cancel.type = "button";
        consent.append(confirm, cancel);
        consent.hidden = false;
        confirm.addEventListener("click", async () => {
          confirm.disabled = true;
          updateStatus.textContent = "Installing Sonder update…";
          try {
            const installed = await services.apiClient.post("/api/updates/install", {}, {
              channel: "settings-update-install", owner: "settings-maintenance",
            });
            if (!confirm.isConnected) return;
            const answer = installed.data || {};
            if (!answer.ok) throw new Error(answer.error || "Update installation failed.");
            updateResult.replaceChildren(el(
              documentRef,
              "strong",
              "",
              answer.updated
                ? "Update installed. Restart the Sonder server, then reload this page."
                : answer.message || "Sonder is already up to date.",
            ));
            updateStatus.textContent = "";
          } catch (error) {
            updateStatus.textContent = error?.userMessage || error?.message || "Sonder could not install the update.";
            if (confirm.isConnected) confirm.disabled = false;
          }
        });
        cancel.addEventListener("click", () => {
          consent.hidden = true;
          installUpdate.focus();
        });
      });
      updateResult.append(installUpdate, consent);
    } catch (error) {
      if (checkUpdates.isConnected) updateStatus.textContent = error?.userMessage || error?.message || "Sonder could not check for updates.";
    } finally {
      if (checkUpdates.isConnected) checkUpdates.disabled = false;
    }
  });

  const checkpoints = el(documentRef, "section", "ui-settings__group");
  const checkpointCopy = el(documentRef, "span", "ui-settings__field-copy");
  checkpointCopy.append(
    el(documentRef, "strong", "", "Checkpoint storage"),
    el(documentRef, "small", "", "Older checkpoints may store duplicate memory vectors. Conversion changes storage only; it does not re-embed memories."),
  );
  const checkpointResult = el(documentRef, "div", "ui-settings__maintenance-result", "Checking checkpoint storage…");
  checkpointResult.setAttribute("role", "status");
  checkpoints.append(checkpointCopy, checkpointResult);
  const loadCheckpoints = async () => {
    try {
      const result = await services.apiClient.get("/api/maintenance/checkpoints", {
        channel: "settings-checkpoint-status", owner: "settings-maintenance",
      });
      if (!checkpoints.isConnected) return;
      const report = result.data || {};
      checkpointResult.replaceChildren();
      if (report.error) {
        checkpointResult.append(el(documentRef, "p", "ui-settings__extension-error", report.error));
        return;
      }
      const progress = report.progress || {};
      if (progress.running) {
        const total = Number(progress.total || 0);
        const done = Number(progress.done || 0);
        const progressElement = documentRef.createElement("progress");
        progressElement.max = total || 1;
        progressElement.value = done;
        checkpointResult.append(
          el(documentRef, "p", "", `Converting ${done.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} checkpoints.`),
          progressElement,
        );
        setTimeout(loadCheckpoints, 1000);
        return;
      }
      const total = Number(report.checkpoints || 0);
      const legacy = Number(report.legacy || 0);
      if (!total) {
        checkpointResult.append(el(documentRef, "p", "", "No checkpoints are stored yet."));
        return;
      }
      if (!legacy) {
        checkpointResult.append(el(documentRef, "p", "", `All ${total.toLocaleString("en-US")} checkpoints use the current format.`));
        return;
      }
      checkpointResult.append(
        el(documentRef, "p", "", `${legacy.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} checkpoints use the legacy format.`),
        el(documentRef, "p", "ui-muted", "Conversion is resumable and leaves any checkpoint that fails its equivalence check untouched."),
      );
      const convert = el(documentRef, "button", "ui-button ui-button--quiet", "Convert legacy checkpoints");
      convert.type = "button";
      const consent = el(documentRef, "div", "ui-settings__extension-consent");
      consent.hidden = true;
      convert.addEventListener("click", () => {
        consent.replaceChildren(
          el(documentRef, "strong", "", "Convert legacy checkpoints?"),
          el(documentRef, "p", "", "Rollback history will be rewritten into the current storage format."),
        );
        const confirm = el(documentRef, "button", "ui-button ui-button--primary", "Confirm checkpoint conversion");
        confirm.type = "button";
        const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
        cancel.type = "button";
        consent.append(confirm, cancel);
        consent.hidden = false;
        confirm.addEventListener("click", async () => {
          confirm.disabled = true;
          try {
            const started = await services.apiClient.post("/api/maintenance/checkpoints/compact", {}, {
              channel: "settings-checkpoint-convert", owner: "settings-maintenance",
            });
            if (!confirm.isConnected) return;
            const answer = started.data || {};
            checkpointResult.replaceChildren(el(
              documentRef,
              "p",
              "",
              answer.started === false
                ? `Checkpoint conversion was not started: ${answer.reason || "nothing to convert"}.`
                : `Checkpoint conversion started for ${Number(answer.total || legacy).toLocaleString("en-US")} checkpoints.`,
            ));
          } catch (error) {
            if (confirm.isConnected) {
              confirm.disabled = false;
              consent.append(el(documentRef, "p", "ui-settings__extension-error", error?.userMessage || error?.message || "Sonder could not start checkpoint conversion."));
            }
          }
        });
        cancel.addEventListener("click", () => {
          consent.hidden = true;
          convert.focus();
        });
      });
      checkpointResult.append(convert, consent);
    } catch (error) {
      if (checkpoints.isConnected) checkpointResult.textContent = error?.userMessage || error?.message || "Sonder could not check checkpoint storage.";
    }
  };
  section.append(head, updates, checkpoints);
  queueMicrotask(loadCheckpoints);
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
    const cacheLabel = el(documentRef, "label", "ui-settings__provider-cache");
    const cache = documentRef.createElement("input");
    cache.type = "checkbox";
    cache.checked = Boolean(provider.prompt_cache);
    cache.disabled = Boolean(provider.prompt_cache_locked);
    cache.setAttribute("aria-label", `Cache repeated prompts for ${provider.name || provider.kind || "provider"}`);
    cacheLabel.append(cache, el(documentRef, "span", "", "Prompt cache"));
    const status = el(documentRef, "p", "ui-settings__provider-status");
    status.setAttribute("role", "status");
    cache.addEventListener("change", async () => {
      const requested = cache.checked;
      cache.disabled = true;
      status.textContent = "Saving prompt cache preference…";
      try {
        const result = await services.apiClient.put(`/api/providers/${provider.id}/prompt_cache`, {
          enabled: requested,
        }, {
          channel: `settings-provider-cache:${provider.id}`,
          owner: `settings-provider:${provider.id}`,
        });
        if (!cache.isConnected) return;
        const enabled = Boolean(result.data?.prompt_cache);
        cache.checked = enabled;
        status.textContent = `Prompt caching ${enabled ? "remains on" : "is off"} for ${provider.name || provider.kind || "this provider"}.`;
      } catch (error) {
        if (!cache.isConnected) return;
        cache.checked = !requested;
        status.textContent = error?.userMessage || error?.message || "Sonder could not change prompt caching.";
      } finally {
        if (cache.isConnected) cache.disabled = Boolean(provider.prompt_cache_locked);
      }
    });
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
    row.append(icon(documentRef, "api"), copy, credential, cacheLabel, edit, test, status);
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

  const limitBounds = data.max_output_tokens_bounds || { min: 1024, max: 128000, default: 20000 };
  const limitGroup = el(documentRef, "section", "ui-settings__group");
  const limitHead = el(documentRef, "div", "ui-settings__field-head");
  const limitCopy = el(documentRef, "span", "ui-settings__field-copy");
  limitCopy.append(
    el(documentRef, "strong", "", "Response limit"),
    el(documentRef, "small", "", "Caps the output requested from any one model call. Specialized stages keep their smaller limits."),
  );
  const limitControl = el(documentRef, "span", "ui-settings__inline-control");
  const limit = documentRef.createElement("input");
  limit.type = "number";
  limit.min = String(limitBounds.min);
  limit.max = String(limitBounds.max);
  limit.step = "1000";
  limit.value = String(data.max_output_tokens ?? limitBounds.default);
  limit.setAttribute("aria-label", "Maximum output tokens");
  const saveLimit = el(documentRef, "button", "ui-button ui-button--quiet", "Save response limit");
  saveLimit.type = "button";
  limitControl.append(limit, saveLimit);
  limitHead.append(limitCopy, limitControl);
  const limitStatus = el(documentRef, "p", "ui-settings__connection-status");
  limitStatus.setAttribute("role", "status");
  saveLimit.addEventListener("click", async () => {
    saveLimit.disabled = true;
    limitStatus.textContent = "Saving response limit…";
    try {
      const result = await services.apiClient.put("/api/max_output_tokens", { value: limit.value }, {
        channel: "settings-output-limit",
        owner: "settings-generation-defaults",
      });
      if (!saveLimit.isConnected) return;
      const saved = Number(result.data?.value);
      if (Number.isFinite(saved)) limit.value = String(saved);
      limitStatus.textContent = `Response limit saved: ${Number(limit.value).toLocaleString("en-US")} tokens.`;
    } catch (error) {
      if (!saveLimit.isConnected) return;
      limitStatus.textContent = error?.userMessage || error?.message || "Sonder could not save the response limit.";
    } finally {
      if (saveLimit.isConnected) saveLimit.disabled = false;
    }
  });
  limitGroup.append(limitHead, limitStatus);

  const assignments = documentRef.createElement("details");
  assignments.className = "ui-settings__group ui-settings__model-assignments";
  const assignmentsSummary = el(documentRef, "summary", "ui-settings__details-summary", "Advanced model assignments");
  const assignmentsIntro = el(
    documentRef,
    "p",
    "ui-muted",
    "Optional role assignments can use a different model. Blank roles follow Default; embeddings must name a vector model.",
  );
  const assignmentRows = el(documentRef, "div", "ui-settings__assignment-rows");
  const roleNames = Array.isArray(data.roles) ? data.roles : Object.keys(data.agent_models || {});
  const orderedRoles = [...new Set(["default", "embeddings", ...roleNames])].filter(role => role === "default" || role === "embeddings" || roleNames.includes(role));
  const roleControls = new Map();
  const effortLevels = Array.isArray(data.reasoning_effort_levels)
    ? data.reasoning_effort_levels : ["off", "minimal", "low", "medium", "high"];
  orderedRoles.forEach(role => {
    const label = humanizeSettingKey(role);
    const existing = data.agent_models?.[role] || {};
    const row = el(documentRef, "fieldset", "ui-settings__assignment-row");
    row.append(el(documentRef, "legend", "", label));
    const providerField = el(documentRef, "label", "ui-field");
    providerField.append(el(documentRef, "span", "ui-field__label", "Provider"));
    const providerSelect = documentRef.createElement("select");
    providerSelect.setAttribute("aria-label", `Provider for ${label}`);
    const emptyProvider = el(documentRef, "option", "", role === "default" || role === "embeddings" ? "Not configured" : "Follow Default");
    emptyProvider.value = "";
    providerSelect.append(emptyProvider);
    providers.forEach(provider => {
      const option = el(documentRef, "option", "", provider.name || provider.kind || `Provider ${provider.id}`);
      option.value = String(provider.id);
      option.selected = String(existing.provider ?? "") === String(provider.id);
      providerSelect.append(option);
    });
    providerField.append(providerSelect);
    const modelField = el(documentRef, "label", "ui-field");
    modelField.append(el(documentRef, "span", "ui-field__label", "Model"));
    const modelInput = documentRef.createElement("input");
    modelInput.type = "text";
    modelInput.value = existing.model || "";
    modelInput.placeholder = role === "embeddings" ? "Vector model id" : "Model id";
    modelInput.setAttribute("aria-label", `Model for ${label}`);
    modelField.append(modelInput);
    const effortField = el(documentRef, "label", "ui-field");
    effortField.append(el(documentRef, "span", "ui-field__label", "Reasoning"));
    const effort = documentRef.createElement("select");
    effort.setAttribute("aria-label", `Reasoning effort for ${label}`);
    const inherited = el(documentRef, "option", "", role === "default" ? "Model default" : "Follow Default");
    inherited.value = "";
    effort.append(inherited);
    effortLevels.forEach(level => {
      const option = el(documentRef, "option", "", humanizeSettingKey(level));
      option.value = level;
      option.selected = data.reasoning_effort?.[role] === level;
      effort.append(option);
    });
    effortField.append(effort);
    row.append(providerField, modelField, effortField);
    assignmentRows.append(row);
    roleControls.set(role, { providerSelect, modelInput, effort });
  });
  const assignmentFooter = el(documentRef, "div", "ui-settings__connection-footer");
  const assignmentStatus = el(documentRef, "p", "ui-settings__connection-status");
  assignmentStatus.setAttribute("role", "status");
  const embeddingNotice = el(documentRef, "p", "ui-settings__warning-inline");
  embeddingNotice.hidden = true;
  const saveAssignments = el(documentRef, "button", "ui-button ui-button--primary", "Save model assignments");
  saveAssignments.type = "button";
  assignmentFooter.append(saveAssignments);
  saveAssignments.addEventListener("click", async () => {
    saveAssignments.disabled = true;
    assignmentStatus.textContent = "Saving model assignments…";
    const nextModels = structuredClone(data.agent_models || {});
    const efforts = {};
    for (const [role, controls] of roleControls.entries()) {
      const providerId = controls.providerSelect.value;
      const model = controls.modelInput.value.trim();
      if (!providerId || !model) {
        delete nextModels[role];
        continue;
      }
      const provider = providers.find(item => String(item.id) === providerId);
      nextModels[role] = {
        ...(nextModels[role] || {}),
        provider: provider?.id ?? providerId,
        model,
      };
      if (controls.effort.value) efforts[role] = controls.effort.value;
    }
    try {
      const modelsResult = await services.apiClient.put("/api/agent_models", nextModels, {
        channel: "settings-agent-models-save",
        owner: "settings-agent-models",
      });
      await services.apiClient.put("/api/reasoning_effort", { efforts }, {
        channel: "settings-reasoning-effort-save",
        owner: "settings-agent-models",
      });
      if (!saveAssignments.isConnected) return;
      assignmentStatus.textContent = "Model assignments saved.";
      if (modelsResult.data?.embeddings_role_changed) {
        embeddingNotice.textContent = "Memory vectors need rebuilding for the new embeddings model.";
        embeddingNotice.hidden = false;
      }
    } catch (error) {
      if (!saveAssignments.isConnected) return;
      assignmentStatus.textContent = error?.userMessage || error?.message || "Sonder could not save model assignments.";
    } finally {
      if (saveAssignments.isConnected) saveAssignments.disabled = false;
    }
  });
  assignments.append(assignmentsSummary, assignmentsIntro, assignmentRows, assignmentStatus, embeddingNotice, assignmentFooter);

  const backdropConfig = data.image_model || {};
  const backdrops = el(documentRef, "section", "ui-settings__group");
  const backdropTitle = el(documentRef, "div", "ui-settings__field-copy");
  backdropTitle.append(
    el(documentRef, "strong", "", "Scene backdrops"),
    el(documentRef, "small", "", "Generate and cache a room image from its spatial description. People are never included."),
  );
  const backdropFields = el(documentRef, "div", "ui-settings__media-fields");
  const backdropProviderField = el(documentRef, "label", "ui-field");
  backdropProviderField.append(el(documentRef, "span", "ui-field__label", "Provider"));
  const backdropProvider = documentRef.createElement("select");
  backdropProvider.setAttribute("aria-label", "Backdrop image provider");
  const noBackdropProvider = el(documentRef, "option", "", "Not configured");
  noBackdropProvider.value = "";
  backdropProvider.append(noBackdropProvider);
  providers.forEach(provider => {
    const option = el(documentRef, "option", "", provider.name || provider.kind || `Provider ${provider.id}`);
    option.value = String(provider.id);
    option.selected = String(backdropConfig.provider ?? "") === String(provider.id);
    backdropProvider.append(option);
  });
  backdropProviderField.append(backdropProvider);
  const backdropModelField = el(documentRef, "label", "ui-field");
  backdropModelField.append(el(documentRef, "span", "ui-field__label", "Image model"));
  const backdropModel = documentRef.createElement("input");
  backdropModel.type = "text";
  backdropModel.value = backdropConfig.model || "";
  backdropModel.setAttribute("aria-label", "Backdrop image model");
  backdropModelField.append(backdropModel);
  const backdropSizeField = el(documentRef, "label", "ui-field");
  backdropSizeField.append(el(documentRef, "span", "ui-field__label", "Landscape size"));
  const backdropSize = documentRef.createElement("input");
  backdropSize.type = "text";
  backdropSize.value = backdropConfig.size || "";
  backdropSize.placeholder = "1536x1024";
  backdropSize.setAttribute("aria-label", "Backdrop image size");
  backdropSizeField.append(backdropSize);
  backdropFields.append(backdropProviderField, backdropModelField, backdropSizeField);
  const backdropToggles = el(documentRef, "div", "ui-settings__media-toggles");
  const backdropEnabledLabel = el(documentRef, "label", "");
  const backdropEnabled = documentRef.createElement("input");
  backdropEnabled.type = "checkbox";
  backdropEnabled.checked = Boolean(data.backdrops_enabled);
  backdropEnabled.setAttribute("aria-label", "Generate backdrops for new rooms");
  backdropEnabledLabel.append(backdropEnabled, documentRef.createTextNode(" Generate backdrops for new rooms"));
  const continuityLabel = el(documentRef, "label", "");
  const continuity = documentRef.createElement("input");
  continuity.type = "checkbox";
  continuity.checked = Boolean(data.backdrop_continuity);
  continuity.setAttribute("aria-label", "Keep room images visually consistent");
  continuityLabel.append(continuity, documentRef.createTextNode(" Keep room images visually consistent"));
  backdropToggles.append(backdropEnabledLabel, continuityLabel);
  const backdropFooter = el(documentRef, "div", "ui-settings__connection-footer");
  const backdropStatus = el(documentRef, "p", "ui-settings__connection-status");
  backdropStatus.setAttribute("role", "status");
  const saveBackdrops = el(documentRef, "button", "ui-button ui-button--quiet", "Save backdrop settings");
  saveBackdrops.type = "button";
  backdropFooter.append(saveBackdrops);
  saveBackdrops.addEventListener("click", async () => {
    saveBackdrops.disabled = true;
    backdropStatus.textContent = "Saving backdrop settings…";
    const providerId = backdropProvider.value;
    const provider = providers.find(item => String(item.id) === providerId);
    try {
      await services.apiClient.put("/api/image_model", {
        provider: provider?.id ?? (providerId || null),
        model: backdropModel.value.trim(),
        size: backdropSize.value.trim(),
      }, { channel: "settings-image-model", owner: "settings-backdrops" });
      await services.apiClient.put("/api/backdrops", {
        enabled: backdropEnabled.checked,
        continuity: continuity.checked,
      }, { channel: "settings-backdrops", owner: "settings-backdrops" });
      if (saveBackdrops.isConnected) backdropStatus.textContent = "Backdrop settings saved.";
    } catch (error) {
      if (saveBackdrops.isConnected) backdropStatus.textContent = error?.userMessage || error?.message || "Sonder could not save backdrop settings.";
    } finally {
      if (saveBackdrops.isConnected) saveBackdrops.disabled = false;
    }
  });
  backdrops.append(backdropTitle, backdropFields, backdropToggles, backdropStatus, backdropFooter);

  const ambienceConfig = data.ambience || {};
  const ambience = el(documentRef, "section", "ui-settings__group");
  const ambienceTitle = el(documentRef, "div", "ui-settings__field-copy");
  ambienceTitle.append(
    el(documentRef, "strong", "", "Room ambience"),
    el(documentRef, "small", "", "Play a cached sound bed chosen from the current room, weather, and time."),
  );
  const ambienceFields = el(documentRef, "div", "ui-settings__media-fields");
  const sourceField = el(documentRef, "label", "ui-field");
  sourceField.append(el(documentRef, "span", "ui-field__label", "Source"));
  const source = documentRef.createElement("select");
  source.setAttribute("aria-label", "Ambience source");
  [["local", "Local folder"], ["freesound", "Freesound"]].forEach(([value, label]) => {
    const option = el(documentRef, "option", "", label);
    option.value = value;
    option.selected = ambienceConfig.source === value;
    source.append(option);
  });
  sourceField.append(source);
  const libraryField = el(documentRef, "label", "ui-field");
  libraryField.append(el(documentRef, "span", "ui-field__label", "Local folder"));
  const library = documentRef.createElement("input");
  library.type = "text";
  library.value = ambienceConfig.library || "";
  library.setAttribute("aria-label", "Ambience library folder");
  libraryField.append(library);
  const freesoundField = el(documentRef, "label", "ui-field");
  freesoundField.append(el(documentRef, "span", "ui-field__label", "Freesound API key"));
  const freesoundKey = documentRef.createElement("input");
  freesoundKey.type = "password";
  freesoundKey.autocomplete = "new-password";
  freesoundKey.placeholder = ambienceConfig.has_key ? "Leave blank to keep saved key" : "API key";
  freesoundKey.setAttribute("aria-label", "Freesound API key");
  freesoundField.append(freesoundKey);
  ambienceFields.append(sourceField, libraryField, freesoundField);
  const ambienceToggles = el(documentRef, "div", "ui-settings__media-toggles");
  const ambienceEnabledLabel = el(documentRef, "label", "");
  const ambienceEnabled = documentRef.createElement("input");
  ambienceEnabled.type = "checkbox";
  ambienceEnabled.checked = Boolean(ambienceConfig.enabled);
  ambienceEnabled.setAttribute("aria-label", "Play room ambience");
  ambienceEnabledLabel.append(ambienceEnabled, documentRef.createTextNode(" Play room ambience"));
  ambienceToggles.append(ambienceEnabledLabel);
  const selectedLicenses = new Set(Array.isArray(ambienceConfig.licenses) ? ambienceConfig.licenses : []);
  const licenseInputs = [];
  const availableLicenses = Array.isArray(data.ambience_licenses) ? data.ambience_licenses : [];
  availableLicenses.forEach(license => {
    const label = el(documentRef, "label", "");
    const input = documentRef.createElement("input");
    input.type = "checkbox";
    input.checked = selectedLicenses.has(license);
    input.setAttribute("aria-label", license === "Attribution NonCommercial" ? "Allow NonCommercial sounds" : `Allow ${license} sounds`);
    label.append(input, documentRef.createTextNode(` ${license}`));
    ambienceToggles.append(label);
    licenseInputs.push([license, input]);
  });
  const ambienceFooter = el(documentRef, "div", "ui-settings__connection-footer");
  const ambienceStatus = el(documentRef, "p", "ui-settings__connection-status");
  ambienceStatus.setAttribute("role", "status");
  const saveAmbience = el(documentRef, "button", "ui-button ui-button--quiet", "Save ambience settings");
  saveAmbience.type = "button";
  ambienceFooter.append(saveAmbience);
  saveAmbience.addEventListener("click", async () => {
    saveAmbience.disabled = true;
    ambienceStatus.textContent = "Saving ambience settings…";
    try {
      await services.apiClient.put("/api/ambience", {
        enabled: ambienceEnabled.checked,
        source: source.value,
        library: library.value.trim(),
        freesound_key: freesoundKey.value.trim(),
        licenses: licenseInputs.filter(([, input]) => input.checked).map(([license]) => license),
      }, { channel: "settings-ambience", owner: "settings-ambience" });
      if (saveAmbience.isConnected) ambienceStatus.textContent = "Ambience settings saved.";
    } catch (error) {
      if (saveAmbience.isConnected) ambienceStatus.textContent = error?.userMessage || error?.message || "Sonder could not save ambience settings.";
    } finally {
      if (saveAmbience.isConnected) saveAmbience.disabled = false;
    }
  });
  ambience.append(ambienceTitle, ambienceFields, ambienceToggles, ambienceStatus, ambienceFooter);

  section.append(head, connections, defaults, limitGroup, assignments, backdrops, ambience);
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
      : active === "content"
        ? contentSettings(documentRef, services, state)
      : active === "add-ons"
        ? addOnsSettings(documentRef, services)
      : active === "maintenance"
        ? maintenanceSettings(documentRef, services)
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
