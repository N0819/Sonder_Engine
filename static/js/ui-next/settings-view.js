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

const LEGACY_THEMES = Object.freeze([
  ["sonder", "Sonder", "carbon-signal"],
  ["tavern", "Tavern", "ash-brass"],
  ["lcars", "LCARS", "carbon-signal"],
  ["stone", "Stone", "ash-brass"],
  ["ink", "Ink", "midnight-ink"],
]);

const SETTINGS_INDEX = Object.freeze([
  ["experience", "themes", "Themes", "appearance palette colors legacy skin"],
  ["experience", "reading", "Reading and effects", "story text prose size density spacing motion visual effects"],
  ["experience", "sound", "Sound, notifications, and language", "volume mute chime notify interface translation locale"],
  ["experience", "accessibility", "Accessibility", "contrast motion focus large text roomy controls"],
  ["ai-connections", "providers", "Provider credentials", "api key token endpoint connection provider"],
  ["ai-connections", "models", "Models and roles", "model defaults backup sampler reasoning openrouter routing"],
  ["content", "content-permissions", "Story content", "adult mature nsfw underneath attire promotion"],
  ["add-ons", "extensions", "Extensions", "addon plugin install permissions enable update remove recovery"],
  ["maintenance", "updates", "Sonder updates", "upgrade version git restart"],
  ["maintenance", "memory-search", "Memory search repair", "embedding vectors rebuild repair"],
  ["maintenance", "diagnostics", "Diagnostics", "logs errors report download"],
  ["advanced", "prompts", "Prompt editor", "prompt preset sheets instructions"],
  ["advanced", "story-data", "Raw story data", "world json technical"],
  ["advanced", "clothing-data", "Raw clothing data", "attire json technical"],
]);

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

function settingsSearch(documentRef, services) {
  const field = el(documentRef, "div", "ui-settings__search-wrap");
  const label = el(documentRef, "label", "ui-settings__search");
  const input = documentRef.createElement("input");
  input.type = "search";
  input.placeholder = "Search settings";
  input.setAttribute("aria-label", "Search settings");
  input.setAttribute("aria-controls", "settings-search-results");
  const results = el(documentRef, "div", "ui-settings__search-results");
  results.id = "settings-search-results";
  results.hidden = true;
  const close = () => {
    results.hidden = true;
    results.replaceChildren();
  };
  const render = () => {
    const query = input.value.trim().toLocaleLowerCase();
    results.replaceChildren();
    if (!query) {
      close();
      return;
    }
    const words = query.split(/\s+/).filter(Boolean);
    const matches = SETTINGS_INDEX.filter(([, , labelText, aliases]) => {
      const haystack = `${labelText} ${aliases}`.toLocaleLowerCase();
      return words.every(word => haystack.includes(word));
    });
    if (!matches.length) {
      results.append(el(documentRef, "p", "ui-muted", "No settings match that search."));
      results.hidden = false;
      return;
    }
    matches.forEach(([category, control, labelText]) => {
      const categoryLabel = CATEGORIES.find(([id]) => id === category)?.[1] || category;
      const button = el(documentRef, "button", "ui-settings__search-result", `${labelText} · ${categoryLabel}`);
      button.type = "button";
      button.addEventListener("click", () => services.router.navigate({
        destination: "settings",
        segments: [category],
        query: { control },
      }));
      results.append(button);
    });
    results.hidden = false;
  };
  input.addEventListener("input", render);
  input.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      close();
      input.focus();
    }
  });
  label.append(icon(documentRef, "search"), input);
  field.append(label, results);
  return field;
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
    delete documentRef.documentElement.dataset.legacyTheme;
    const stored = services.localState.snapshot().appearance || {};
    services.localState.setRecord("appearance", { ...stored, theme: id, legacyTheme: undefined });
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

function livingWorldSettings(documentRef, services, state) {
  const chatId = Number(state.story?.data?.chat?.id || state.library?.chats?.[0]?.id || 0);
  const group = el(documentRef, "section", "ui-settings__group ui-settings__living-world");
  const copy = el(documentRef, "span", "ui-settings__field-copy");
  copy.append(
    el(documentRef, "strong", "", "Living world"),
    el(documentRef, "small", "", "Choose which world mechanisms may run outside the current scene. Requested depth is visibly clamped to what is built and what this story permits."),
  );
  const body = el(documentRef, "div", "ui-settings__maintenance-result", chatId ? "Loading this story's world settings…" : "Open a story to configure its living world.");
  body.setAttribute("role", "status");
  group.append(copy, body);
  if (!chatId) return group;
  queueMicrotask(async () => {
    try {
      const result = await services.apiClient.get(`/api/chats/${chatId}/living_world`, {
        channel: `settings-living-world:${chatId}`, owner: `story:${chatId}`,
      });
      if (!group.isConnected) return;
      const report = result.data || {};
      const controls = new Map();
      const rows = el(documentRef, "div", "ui-settings__living-world-rows");
      for (const approach of report.approaches || []) {
        const row = el(documentRef, "div", "ui-settings__living-world-row");
        const rowCopy = el(documentRef, "span", "ui-settings__field-copy");
        const floor = (approach.depths || []).find(depth => depth.value === "floor");
        rowCopy.append(
          el(documentRef, "strong", "", approach.label || humanizeSettingKey(approach.approach)),
          el(documentRef, "small", "", floor?.description || approach.cost || ""),
        );
        const control = documentRef.createElement("select");
        control.setAttribute("aria-label", `${approach.label || humanizeSettingKey(approach.approach)} depth`);
        const off = el(documentRef, "option", "", "Off");
        off.value = "off";
        off.selected = approach.value === "off";
        control.append(off);
        for (const depth of approach.depths || []) {
          const option = el(documentRef, "option", "", depth.built ? humanizeSettingKey(depth.value) : `${humanizeSettingKey(depth.value)} — not built yet`);
          option.value = depth.value;
          option.selected = approach.value === depth.value;
          control.append(option);
        }
        const effective = el(documentRef, "p", "ui-settings__living-world-effective");
        const selectedDepth = (approach.depths || []).find(depth => depth.value === approach.value);
        if (approach.effective !== approach.value) {
          const reason = selectedDepth && !selectedDepth.built
            ? `${humanizeSettingKey(approach.value)} is not built yet.`
            : `the story's off-screen limit does not permit ${humanizeSettingKey(approach.value)}.`;
          effective.textContent = `Runs as ${humanizeSettingKey(approach.effective)} — ${reason}`;
        } else effective.textContent = `Runs as ${humanizeSettingKey(approach.effective)}.`;
        const field = el(documentRef, "span", "ui-settings__living-world-control");
        field.append(control, effective, el(documentRef, "small", "ui-muted", approach.cost || ""));
        row.append(rowCopy, field);
        rows.append(row);
        controls.set(approach.approach, control);
      }
      const status = el(documentRef, "p", "ui-settings__connection-status");
      status.setAttribute("role", "status");
      const footer = el(documentRef, "div", "ui-settings__connection-footer");
      const save = el(documentRef, "button", "ui-button ui-button--primary", "Save living world settings");
      save.type = "button";
      footer.append(save);
      save.addEventListener("click", async () => {
        save.disabled = true;
        status.textContent = "Saving living world settings…";
        try {
          await services.apiClient.put(`/api/chats/${chatId}/living_world`, {
            living_world: Object.fromEntries([...controls].map(([key, control]) => [key, control.value])),
          }, { channel: `settings-living-world:${chatId}`, owner: `story:${chatId}` });
          if (save.isConnected) status.textContent = "Living world settings saved.";
        } catch (error) {
          if (save.isConnected) status.textContent = error?.userMessage || error?.message || "Sonder could not save living world settings.";
        } finally {
          if (save.isConnected) save.disabled = false;
        }
      });
      body.replaceChildren(rows, status, footer);
    } catch (error) {
      if (group.isConnected) body.textContent = error?.userMessage || error?.message || "Sonder could not load living world settings.";
    }
  });
  return group;
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
  themeGroup.id = "settings-control-themes";
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
  const emptyLegacy = el(documentRef, "option", "", "Choose a legacy theme");
  emptyLegacy.value = "";
  select.append(emptyLegacy);
  const storedLegacy = services.localState.snapshot().appearance?.legacyTheme || "";
  LEGACY_THEMES.forEach(([id, label]) => {
    const option = el(documentRef, "option", "", label);
    option.value = id;
    option.selected = id === storedLegacy;
    select.append(option);
  });
  select.addEventListener("change", () => {
    const selected = LEGACY_THEMES.find(([id]) => id === select.value);
    if (!selected) return;
    const [legacyId, , semanticTheme] = selected;
    appearance.setTheme(semanticTheme);
    documentRef.documentElement.dataset.legacyTheme = legacyId;
    const stored = services.localState.snapshot().appearance || {};
    services.localState.setRecord("appearance", { ...stored, theme: semanticTheme, legacyTheme: legacyId });
    themeGroup.querySelector(".ui-settings__theme-readout")?.replaceChildren(`Legacy · ${selected[1]}`);
    themes.querySelectorAll("[data-theme-choice]").forEach(choice => {
      const activeChoice = choice.dataset.themeChoice === semanticTheme;
      choice.setAttribute("aria-pressed", String(activeChoice));
      choice.querySelector(".ui-settings__theme-status").textContent = activeChoice ? "Mapped" : "Use";
    });
  });
  legacy.append(legacyCopy, select);
  themeGroup.append(themeHead, themes, legacy);

  const readingGroup = el(documentRef, "section", "ui-settings__group");
  readingGroup.id = "settings-control-reading";
  const appearanceState = services.localState.snapshot().appearance || {};
  const localSelectRow = (label, detail, ariaLabel, options, current, onChange) => {
    const row = el(documentRef, "div", "ui-settings__field-head");
    const rowCopy = el(documentRef, "span", "ui-settings__field-copy");
    rowCopy.append(el(documentRef, "strong", "", label), el(documentRef, "small", "", detail));
    const control = documentRef.createElement("select");
    control.setAttribute("aria-label", ariaLabel);
    options.forEach(([value, optionLabel]) => {
      const option = el(documentRef, "option", "", optionLabel);
      option.value = value;
      option.selected = String(current) === value;
      control.append(option);
    });
    control.addEventListener("change", () => onChange(control.value));
    row.append(rowCopy, control);
    return row;
  };
  readingGroup.append(
    localSelectRow(
      "Story text size",
      "Changes story prose without enlarging the surrounding controls.",
      "Story text size",
      [["15", "Small"], ["17", "Standard"], ["19", "Large"], ["21", "Extra large"]],
      documentRef.documentElement.dataset.proseSize || appearanceState.proseSize || "17",
      value => {
        appearance.setProseSize(value);
        services.localState.setRecord("appearance", { ...services.localState.snapshot().appearance, proseSize: value });
      },
    ),
    localSelectRow(
      "Interface density",
      "Changes spacing while keeping every control available.",
      "Interface density",
      [["compact", "Compact"], ["comfortable", "Comfortable"], ["roomy", "Roomy"]],
      documentRef.documentElement.dataset.density || appearanceState.density || "comfortable",
      value => {
        documentRef.documentElement.dataset.density = value;
        services.localState.setRecord("appearance", { ...services.localState.snapshot().appearance, density: value });
      },
    ),
    localSelectRow(
      "Visual effects",
      "Reduce or stop decorative weather, hearth, and backdrop transitions.",
      "Visual effects",
      [["full", "Full"], ["reduced", "Reduced"], ["off", "Off"]],
      documentRef.documentElement.dataset.effects || appearanceState.effects || "full",
      value => {
        appearance.setEffects(value);
        services.localState.setRecord("appearance", { ...services.localState.snapshot().appearance, effects: value });
      },
    ),
  );

  const soundGroup = el(documentRef, "section", "ui-settings__group");
  soundGroup.id = "settings-control-sound";
  const soundPreferences = services.atmosphere.snapshot()?.preferences || { muted: false, volume: 0.7, chime: false };
  const volumeRow = el(documentRef, "div", "ui-settings__field-head");
  const volumeCopy = el(documentRef, "span", "ui-settings__field-copy");
  volumeCopy.append(el(documentRef, "strong", "", "Story sound"), el(documentRef, "small", "", "Controls room ambience and the optional turn-complete chime on this device."));
  const soundControls = el(documentRef, "div", "ui-settings__sound-controls");
  const volume = documentRef.createElement("input");
  volume.type = "range";
  volume.min = "0";
  volume.max = "1";
  volume.step = "0.05";
  volume.value = String(soundPreferences.volume ?? 0.7);
  volume.setAttribute("aria-label", "Sound volume");
  volume.addEventListener("input", () => services.atmosphere.setVolume(volume.value));
  const muted = documentRef.createElement("input");
  muted.type = "checkbox";
  muted.checked = Boolean(soundPreferences.muted);
  muted.setAttribute("aria-label", "Mute story sound");
  muted.addEventListener("change", () => services.atmosphere.setMuted(muted.checked));
  const muteLabel = el(documentRef, "label", "");
  muteLabel.append(muted, documentRef.createTextNode(" Mute story sound"));
  const chime = documentRef.createElement("input");
  chime.type = "checkbox";
  chime.checked = Boolean(soundPreferences.chime);
  chime.setAttribute("aria-label", "Notify when a turn finishes");
  chime.addEventListener("change", () => services.atmosphere.setChime(chime.checked));
  const chimeLabel = el(documentRef, "label", "");
  chimeLabel.append(chime, documentRef.createTextNode(" Notify when a turn finishes"));
  soundControls.append(volume, muteLabel, chimeLabel);
  volumeRow.append(volumeCopy, soundControls);
  soundGroup.append(volumeRow);

  const languagePacks = Array.isArray(services.store.getSnapshot().settings?.data?.language_packs)
    ? services.store.getSnapshot().settings.data.language_packs.filter(pack => pack.ui !== false) : [];
  if (languagePacks.length) {
    const languageRow = el(documentRef, "div", "ui-settings__field-head");
    const languageCopy = el(documentRef, "span", "ui-settings__field-copy");
    languageCopy.append(el(documentRef, "strong", "", "Interface language"), el(documentRef, "small", "", "Applies to menus and controls after reload. Story language is chosen per story."));
    const languageControls = el(documentRef, "div", "ui-settings__inline-control");
    const language = documentRef.createElement("select");
    language.setAttribute("aria-label", "Interface language");
    languagePacks.forEach(pack => {
      const option = el(documentRef, "option", "", pack.native_name || pack.name || pack.id);
      option.value = pack.id;
      option.selected = pack.id === services.store.getSnapshot().settings.data.ui_language;
      language.append(option);
    });
    const applyLanguage = el(documentRef, "button", "ui-button ui-button--quiet", "Apply interface language");
    applyLanguage.type = "button";
    const languageStatus = el(documentRef, "p", "ui-settings__connection-status");
    languageStatus.setAttribute("role", "status");
    applyLanguage.addEventListener("click", async () => {
      applyLanguage.disabled = true;
      languageStatus.textContent = "Saving language…";
      try {
        await services.apiClient.put("/api/ui-language", { language: language.value }, {
          channel: "settings-ui-language", owner: "settings-experience",
        });
        if (applyLanguage.isConnected) languageStatus.textContent = "Language saved. Reload Sonder to apply it everywhere.";
      } catch (error) {
        if (applyLanguage.isConnected) languageStatus.textContent = error?.userMessage || error?.message || "Sonder could not save the interface language.";
      } finally {
        if (applyLanguage.isConnected) applyLanguage.disabled = false;
      }
    });
    languageControls.append(language, applyLanguage);
    languageRow.append(languageCopy, languageControls);
    soundGroup.append(languageRow, languageStatus);
  }

  const accessibilityGroup = el(documentRef, "section", "ui-settings__group");
  accessibilityGroup.id = "settings-control-accessibility";
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
  const resetGroup = el(documentRef, "section", "ui-settings__group ui-settings__data-note");
  const resetCopy = el(documentRef, "span", "ui-settings__field-copy");
  resetCopy.append(
    el(documentRef, "strong", "", "Reset Experience on this device"),
    el(documentRef, "small", "", "Restores Carbon Signal, standard story text, comfortable spacing, full effects, sound defaults, and accessibility controls. Stories and host settings are unchanged."),
  );
  const reset = el(documentRef, "button", "ui-button ui-button--quiet", "Reset Experience");
  reset.type = "button";
  const resetConsent = el(documentRef, "div", "ui-settings__extension-consent");
  resetConsent.hidden = true;
  reset.addEventListener("click", () => {
    resetConsent.replaceChildren(
      el(documentRef, "strong", "", "Reset Experience on this device?"),
      el(documentRef, "p", "", "This is reversible by choosing the preferences again. Stories are not changed."),
    );
    const confirm = el(documentRef, "button", "ui-button ui-button--primary", "Confirm reset Experience");
    confirm.type = "button";
    const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
    cancel.type = "button";
    resetConsent.append(confirm, cancel);
    resetConsent.hidden = false;
    confirm.addEventListener("click", () => {
      appearance.setTheme("carbon-signal");
      appearance.setProseSize("17");
      appearance.setEffects("full");
      documentRef.documentElement.dataset.density = "comfortable";
      delete documentRef.documentElement.dataset.legacyTheme;
      services.atmosphere.setMuted(false);
      services.atmosphere.setVolume(0.7);
      services.atmosphere.setChime(false);
      services.localState.setRecord("appearance", { theme: "carbon-signal", proseSize: "17", effects: "full", density: "comfortable" });
      const resetAccessibility = Object.fromEntries(ACCESSIBILITY.map(([key]) => [key, false]));
      syncAccessibility(updateAccessibility(resetAccessibility));
      resetConsent.replaceChildren(el(documentRef, "p", "", "Experience settings reset on this device."));
    });
    cancel.addEventListener("click", () => {
      resetConsent.hidden = true;
      reset.focus();
    });
  });
  resetGroup.append(resetCopy, reset, resetConsent);
  section.append(head, themeGroup, readingGroup, soundGroup, accessibilityGroup, resetGroup);
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
  permissions.id = "settings-control-content-permissions";
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
  const resetContent = el(documentRef, "button", "ui-button ui-button--quiet", "Reset content form");
  resetContent.type = "button";
  resetContent.addEventListener("click", () => {
    [adult, beneath, promote].forEach(control => {
      control.input.checked = false;
      control.row.querySelector(".ui-settings__toggle-state").textContent = "Off";
    });
    status.textContent = "Content form reset to the safest defaults. Choose Save content preferences to apply it.";
  });
  actions.append(resetContent, save);
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
    el(documentRef, "small", "", "Imports, portable exports, and permanent deletion remain attached to the specific story or Library item, so a broad control cannot overwrite or erase the wrong data."),
  );
  const manage = el(documentRef, "a", "ui-button ui-button--quiet", "Manage story exports and deletion");
  manage.href = "#/library/stories";
  localData.append(dataCopy, manage);
  section.append(head, permissions, localData, livingWorldSettings(documentRef, services, state));
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
  list.id = "settings-control-extensions";
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
  updates.id = "settings-control-updates";
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
  const memorySearch = el(documentRef, "section", "ui-settings__group");
  memorySearch.id = "settings-control-memory-search";
  const memoryCopy = el(documentRef, "span", "ui-settings__field-copy");
  memoryCopy.append(
    el(documentRef, "strong", "", "Memory search"),
    el(documentRef, "small", "", "Check and rebuild stored search vectors after changing the embeddings model."),
  );
  const memoryResult = el(documentRef, "div", "ui-settings__maintenance-result", "Checking memory search…");
  memoryResult.setAttribute("role", "status");
  memorySearch.append(memoryCopy, memoryResult);
  const loadMemory = async () => {
    try {
      const result = await services.apiClient.get("/api/memory/embeddings", {
        channel: "settings-memory-search-status", owner: "settings-maintenance",
      });
      if (!memorySearch.isConnected) return;
      const report = result.data || {};
      memoryResult.replaceChildren();
      if (report.error) {
        memoryResult.append(el(documentRef, "p", "ui-settings__extension-error", report.error));
        return;
      }
      const progress = report.progress || {};
      if (progress.running) {
        const done = Number(progress.done || progress.current || 0);
        const total = Number(progress.total || 0);
        const meter = documentRef.createElement("progress");
        meter.max = total || 1;
        meter.value = done;
        memoryResult.append(el(documentRef, "p", "", `Rebuilding ${done.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} memories.`), meter);
        setTimeout(loadMemory, 1000);
        return;
      }
      const stale = Number(report.stale ?? report.missing ?? Math.max(0, Number(report.total || 0) - Number(report.current || 0)));
      if (!stale) {
        memoryResult.append(el(documentRef, "p", "", "Memory search vectors are current."));
        return;
      }
      memoryResult.append(el(documentRef, "p", "", `${stale.toLocaleString("en-US")} ${stale === 1 ? "memory needs" : "memories need"} updated search vectors.`));
      const rebuild = el(documentRef, "button", "ui-button ui-button--quiet", "Rebuild memory search");
      rebuild.type = "button";
      const consent = el(documentRef, "div", "ui-settings__extension-consent");
      consent.hidden = true;
      rebuild.addEventListener("click", () => {
        consent.replaceChildren(
          el(documentRef, "strong", "", "Rebuild memory search?"),
          el(documentRef, "p", "", "This may use the configured embeddings provider."),
          el(documentRef, "p", "ui-muted", "Stories and memories are not deleted."),
        );
        const confirm = el(documentRef, "button", "ui-button ui-button--primary", "Confirm rebuild memory search");
        confirm.type = "button";
        const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
        cancel.type = "button";
        consent.append(confirm, cancel);
        consent.hidden = false;
        confirm.addEventListener("click", async () => {
          confirm.disabled = true;
          try {
            const started = await services.apiClient.post("/api/memory/embeddings/rebuild", {}, {
              channel: "settings-memory-search-rebuild", owner: "settings-maintenance",
            });
            if (!confirm.isConnected) return;
            const answer = started.data || {};
            memoryResult.replaceChildren(el(documentRef, "p", "", answer.started === false
              ? `Memory search rebuild was not started: ${answer.reason || "nothing to rebuild"}.`
              : `Memory search rebuild started for ${Number(answer.total || stale).toLocaleString("en-US")} memories.`));
          } catch (error) {
            if (confirm.isConnected) {
              confirm.disabled = false;
              consent.append(el(documentRef, "p", "ui-settings__extension-error", error?.userMessage || error?.message || "Sonder could not rebuild memory search."));
            }
          }
        });
        cancel.addEventListener("click", () => {
          consent.hidden = true;
          rebuild.focus();
        });
      });
      memoryResult.append(rebuild, consent);
    } catch (error) {
      if (memorySearch.isConnected) memoryResult.textContent = error?.userMessage || error?.message || "Sonder could not check memory search.";
    }
  };

  const diagnostics = el(documentRef, "section", "ui-settings__group");
  diagnostics.id = "settings-control-diagnostics";
  const diagnosticHead = el(documentRef, "div", "ui-settings__field-head");
  const diagnosticCopy = el(documentRef, "span", "ui-settings__field-copy");
  diagnosticCopy.append(
    el(documentRef, "strong", "", "Diagnostics"),
    el(documentRef, "small", "", "Download the bounded, redacted interface event log. Credentials and request bodies are excluded."),
  );
  const download = el(documentRef, "button", "ui-button ui-button--quiet", "Download redacted diagnostics");
  download.type = "button";
  download.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(services.diagnostics.snapshot(), null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const link = documentRef.createElement("a");
    link.href = href;
    link.download = "sonder-interface-diagnostics.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(href), 0);
  });
  diagnosticHead.append(diagnosticCopy, download);
  diagnostics.append(diagnosticHead);

  const backups = el(documentRef, "section", "ui-settings__group ui-settings__data-note");
  backups.id = "settings-control-backups";
  const backupCopy = el(documentRef, "span", "ui-settings__field-copy");
  backupCopy.append(
    el(documentRef, "strong", "", "Portable story backups"),
    el(documentRef, "small", "", "A story export is a portable backup of that story and its owned data. Exports stay per story so one maintenance action cannot silently expose or overwrite every story."),
  );
  const manageBackups = el(documentRef, "a", "ui-button ui-button--quiet", "Manage portable story backups");
  manageBackups.href = "#/library/stories";
  backups.append(backupCopy, manageBackups);

  section.append(head, updates, checkpoints, memorySearch, diagnostics, backups);
  queueMicrotask(loadCheckpoints);
  queueMicrotask(loadMemory);
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

function promptEditor(documentRef, services, state, route) {
  const data = state.settings?.data || {};
  const presets = data.prompt_presets && typeof data.prompt_presets === "object" ? data.prompt_presets : {};
  const activeName = String(data.active_preset || "Default");
  const selectedName = String(route?.query?.preset || activeName);
  const selected = selectedName === "Default" ? null : presets[selectedName];
  const prompts = { ...(selected?.prompts || data.default_prompts || {}) };
  const editor = el(documentRef, "section", "ui-settings__group ui-settings__prompt-editor");
  editor.id = "settings-control-prompts";
  const header = el(documentRef, "div", "ui-settings__field-head");
  const copy = el(documentRef, "span", "ui-settings__field-copy");
  copy.append(
    el(documentRef, "strong", "", "Prompt preset"),
    el(documentRef, "small", "", "Long-form engine instructions are saved only when you choose Save prompt preset."),
  );
  const back = el(documentRef, "button", "ui-button ui-button--quiet", "Back to Advanced");
  back.type = "button";
  back.addEventListener("click", () => services.router.navigate({ destination: "settings", segments: ["advanced"] }));
  header.append(copy, back);
  const controls = el(documentRef, "div", "ui-settings__prompt-controls");
  const presetField = el(documentRef, "label", "ui-field");
  presetField.append(el(documentRef, "span", "ui-field__label", "Preset"));
  const preset = documentRef.createElement("select");
  preset.setAttribute("aria-label", "Prompt preset");
  ["Default", ...Object.keys(presets).sort()].forEach(presetName => {
    const option = el(documentRef, "option", "", presetName === activeName ? `${presetName} · active` : presetName);
    option.value = presetName;
    option.selected = presetName === selectedName;
    preset.append(option);
  });
  preset.addEventListener("change", () => services.router.navigate({
    destination: "settings", segments: ["advanced"], query: { tool: "prompts", preset: preset.value },
  }, { replace: true }));
  presetField.append(preset);
  const nameField = el(documentRef, "label", "ui-field");
  nameField.append(el(documentRef, "span", "ui-field__label", "Preset name"));
  const name = documentRef.createElement("input");
  name.type = "text";
  name.value = selectedName === "Default" ? "" : selectedName;
  name.setAttribute("aria-label", "Prompt preset name");
  nameField.append(name);
  const languageField = el(documentRef, "label", "ui-field");
  languageField.append(el(documentRef, "span", "ui-field__label", "Story language"));
  const language = documentRef.createElement("select");
  language.setAttribute("aria-label", "Prompt preset language");
  const packs = Array.isArray(data.language_packs) && data.language_packs.length
    ? data.language_packs : [{ id: selected?.language || "en", name: selected?.language || "English" }];
  packs.forEach(pack => {
    const option = el(documentRef, "option", "", pack.name || pack.id);
    option.value = pack.id;
    option.selected = pack.id === (selected?.language || "en");
    language.append(option);
  });
  languageField.append(language);
  controls.append(presetField, nameField, languageField);
  const fields = el(documentRef, "div", "ui-settings__prompt-fields");
  const promptInputs = new Map();
  Object.entries(prompts).sort(([left], [right]) => left.localeCompare(right)).forEach(([id, value]) => {
    const field = el(documentRef, "label", "ui-field ui-settings__prompt-field");
    field.append(el(documentRef, "span", "ui-field__label", humanizeSettingKey(id)));
    const textarea = documentRef.createElement("textarea");
    textarea.value = String(value || "");
    textarea.rows = 10;
    textarea.setAttribute("aria-label", `${humanizeSettingKey(id)} prompt`);
    field.append(textarea);
    fields.append(field);
    promptInputs.set(id, textarea);
  });
  const status = el(documentRef, "p", "ui-settings__connection-status");
  status.setAttribute("role", "status");
  const save = el(documentRef, "button", "ui-button ui-button--primary", "Save prompt preset");
  save.type = "button";
  save.addEventListener("click", async () => {
    const presetName = name.value.trim();
    if (!presetName || presetName === "Default") {
      status.textContent = "Give this editable preset a name first.";
      name.focus();
      return;
    }
    save.disabled = true;
    status.textContent = "Saving prompt preset…";
    try {
      await services.apiClient.put("/api/prompt_presets", {
        name: presetName,
        language: language.value,
        prompts: Object.fromEntries([...promptInputs].map(([id, input]) => [id, input.value])),
      }, { channel: `settings-prompt-preset:${presetName}`, owner: "settings-prompts" });
      if (save.isConnected) status.textContent = "Prompt preset saved.";
    } catch (error) {
      if (save.isConnected) status.textContent = error?.userMessage || error?.message || "Sonder could not save the prompt preset.";
    } finally {
      if (save.isConnected) save.disabled = false;
    }
  });
  const actions = el(documentRef, "div", "ui-settings__prompt-actions");
  const activate = el(documentRef, "button", "ui-button ui-button--quiet", "Use selected preset");
  activate.type = "button";
  activate.disabled = selectedName === activeName;
  activate.addEventListener("click", async () => {
    activate.disabled = true;
    status.textContent = "Changing active prompt preset…";
    try {
      await services.apiClient.put("/api/active_preset", { name: selectedName }, {
        channel: "settings-active-prompt-preset", owner: "settings-prompts",
      });
      if (activate.isConnected) status.textContent = `${selectedName} is now the active prompt preset.`;
    } catch (error) {
      if (activate.isConnected) {
        activate.disabled = false;
        status.textContent = error?.userMessage || error?.message || "Sonder could not change the active prompt preset.";
      }
    }
  });
  const exportPreset = el(documentRef, "button", "ui-button ui-button--quiet", "Export selected preset");
  exportPreset.type = "button";
  exportPreset.disabled = selectedName === "Default";
  exportPreset.addEventListener("click", async () => {
    try {
      const result = await services.apiClient.get(`/api/prompt_presets/${encodeURIComponent(selectedName)}/export`, {
        channel: `settings-prompt-export:${selectedName}`, owner: "settings-prompts",
      });
      const href = URL.createObjectURL(new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" }));
      const link = documentRef.createElement("a");
      link.href = href;
      link.download = `${selectedName}.sonder-prompts.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(href), 0);
      status.textContent = "Prompt preset exported.";
    } catch (error) {
      status.textContent = error?.userMessage || error?.message || "Sonder could not export the prompt preset.";
    }
  });
  const importInput = documentRef.createElement("input");
  importInput.type = "file";
  importInput.accept = "application/json,.json";
  importInput.hidden = true;
  const importPreset = el(documentRef, "button", "ui-button ui-button--quiet", "Import prompt preset");
  importPreset.type = "button";
  importPreset.addEventListener("click", () => importInput.click());
  importInput.addEventListener("change", async () => {
    const file = importInput.files?.[0];
    if (!file) return;
    try {
      const document = JSON.parse(await file.text());
      const result = await services.apiClient.post("/api/prompt_presets/import", { preset: document }, {
        channel: "settings-prompt-import", owner: "settings-prompts",
      });
      status.textContent = `Imported prompt preset ${result.data?.name || "successfully"}.`;
    } catch (error) {
      status.textContent = error?.userMessage || error?.message || "Sonder could not import that prompt preset.";
    }
  });
  const remove = el(documentRef, "button", "ui-button ui-button--danger", "Delete selected preset");
  remove.type = "button";
  remove.disabled = selectedName === "Default";
  const removeConsent = el(documentRef, "div", "ui-settings__extension-consent");
  removeConsent.hidden = true;
  remove.addEventListener("click", () => {
    removeConsent.replaceChildren(
      el(documentRef, "strong", "", `Delete ${selectedName}?`),
      el(documentRef, "p", "", "This removes the saved preset. The engine's built-in Default remains available."),
    );
    const confirm = el(documentRef, "button", "ui-button ui-button--danger", `Confirm delete ${selectedName}`);
    confirm.type = "button";
    const cancel = el(documentRef, "button", "ui-button ui-button--quiet", "Cancel");
    cancel.type = "button";
    removeConsent.append(confirm, cancel);
    removeConsent.hidden = false;
    confirm.addEventListener("click", async () => {
      confirm.disabled = true;
      try {
        await services.apiClient.delete(`/api/prompt_presets/${encodeURIComponent(selectedName)}`, {
          channel: `settings-prompt-delete:${selectedName}`, owner: "settings-prompts",
        });
        services.router.navigate({ destination: "settings", segments: ["advanced"], query: { tool: "prompts", preset: "Default" } }, { replace: true });
      } catch (error) {
        if (confirm.isConnected) {
          confirm.disabled = false;
          removeConsent.append(el(documentRef, "p", "ui-settings__extension-error", error?.userMessage || error?.message || "Sonder could not delete the prompt preset."));
        }
      }
    });
    cancel.addEventListener("click", () => {
      removeConsent.hidden = true;
      remove.focus();
    });
  });
  actions.append(save, activate, exportPreset, importPreset, importInput, remove);
  editor.append(header, controls, fields, status, actions, removeConsent);
  return editor;
}

function rawDataEditor(documentRef, services, state, kind) {
  const isAttire = kind === "clothing-data";
  const chatId = Number(
    state.story?.data?.chat?.id
    || services.router.current().query?.chat
    || state.library?.chats?.[0]?.id
    || 0,
  );
  const label = isAttire ? "Raw clothing data" : "Raw story data";
  const path = chatId ? `/api/chats/${chatId}/${isAttire ? "attire" : "world"}` : "";
  const editor = el(documentRef, "section", "ui-settings__group ui-settings__raw-editor");
  editor.id = `settings-control-${kind}`;
  const header = el(documentRef, "div", "ui-settings__field-head");
  const copy = el(documentRef, "span", "ui-settings__field-copy");
  copy.append(
    el(documentRef, "strong", "", label),
    el(documentRef, "small", "", isAttire
      ? "Correct the current story's clothing and visible-state record. Ordinary play updates this automatically."
      : "Correct the current story's rooms, positions, objects, and standing facts. Ordinary play updates this automatically."),
  );
  const back = el(documentRef, "button", "ui-button ui-button--quiet", "Back to Advanced");
  back.type = "button";
  back.addEventListener("click", () => services.router.navigate({ destination: "settings", segments: ["advanced"] }));
  header.append(copy, back);
  const textarea = documentRef.createElement("textarea");
  textarea.rows = 20;
  textarea.spellcheck = false;
  textarea.setAttribute("aria-label", `${label} JSON`);
  const status = el(documentRef, "p", "ui-settings__connection-status", chatId ? `Loading ${label.toLocaleLowerCase()}…` : "Open a story before using this editor.");
  status.setAttribute("role", "status");
  const save = el(documentRef, "button", "ui-button ui-button--primary", `Save ${label.toLocaleLowerCase()}`);
  save.type = "button";
  save.disabled = !chatId;
  save.addEventListener("click", async () => {
    let body;
    try {
      body = JSON.parse(textarea.value);
    } catch {
      status.textContent = "Enter valid JSON before saving.";
      textarea.focus();
      return;
    }
    save.disabled = true;
    status.textContent = `Saving ${label.toLocaleLowerCase()}…`;
    try {
      await services.apiClient.put(path, body, {
        channel: `settings-raw-${kind}:${chatId}`, owner: `story:${chatId}`,
      });
      if (save.isConnected) status.textContent = `${label} saved.`;
    } catch (error) {
      if (save.isConnected) status.textContent = error?.userMessage || error?.message || `Sonder could not save ${label.toLocaleLowerCase()}.`;
    } finally {
      if (save.isConnected) save.disabled = false;
    }
  });
  editor.append(header, textarea, status, save);
  if (chatId) queueMicrotask(async () => {
    try {
      const result = await services.apiClient.get(path, {
        channel: `settings-raw-${kind}:${chatId}`, owner: `story:${chatId}`,
      });
      if (!textarea.isConnected) return;
      textarea.value = JSON.stringify(result.data, null, 2);
      status.textContent = "Loaded. Changes are not saved until you choose Save.";
    } catch (error) {
      if (textarea.isConnected) status.textContent = error?.userMessage || error?.message || `Sonder could not load ${label.toLocaleLowerCase()}.`;
    }
  });
  return editor;
}

function advanced(documentRef, services, state, route) {
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
    control.id = `settings-control-${id}`;
    const copy = el(documentRef, "span", "ui-settings__launcher-copy");
    copy.append(el(documentRef, "strong", "", label), el(documentRef, "small", "", detail));
    control.append(icon(documentRef, iconName), copy, icon(documentRef, "chevron-right"));
    control.addEventListener("click", () => {
      if (id === "turn-details") {
        services.router.navigate({ destination: "play", segments: ["story-tools"], query: { tool: "turn-details" } });
        return;
      }
      services.router.navigate({ destination: "settings", segments: ["advanced"], query: { tool: id } });
    });
    launchers.append(control);
  });
  const warning = el(documentRef, "aside", "ui-settings__warning");
  const warningCopy = el(documentRef, "span", "ui-settings__launcher-copy");
  warningCopy.append(
    el(documentRef, "strong", "", "Advanced tools change engine-facing data."),
    el(documentRef, "small", "", "Use them when correcting a known problem or diagnosing a turn."),
  );
  warning.append(icon(documentRef, "warning"), warningCopy);
  const tool = String(route?.query?.tool || "");
  section.append(head);
  if (tool === "prompts") section.append(promptEditor(documentRef, services, state, route));
  else if (tool === "story-data" || tool === "clothing-data") section.append(rawDataEditor(documentRef, services, state, tool));
  else section.append(launchers, warning);
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
  addProvider.id = "settings-control-providers";
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

  let openRouterGroup = null;
  if (providers.some(provider => provider.kind === "openrouter")) {
    const routing = data.openrouter_routing || {};
    const splitRouting = value => String(value || "").split(/[\s,]+/).map(item => item.trim()).filter(Boolean);
    openRouterGroup = el(documentRef, "section", "ui-settings__group");
    const routingCopy = el(documentRef, "span", "ui-settings__field-copy");
    routingCopy.append(
      el(documentRef, "strong", "", "OpenRouter upstream routing"),
      el(documentRef, "small", "", "Choose which upstreams may serve a model and whether providers that retain or train on prompts are allowed."),
    );
    const routingFields = el(documentRef, "div", "ui-settings__media-fields");
    const onlyField = el(documentRef, "label", "ui-field");
    onlyField.append(el(documentRef, "span", "ui-field__label", "Allow only"));
    const only = documentRef.createElement("input");
    only.type = "text";
    only.value = (routing.only || []).join(", ");
    only.placeholder = "Blank lets OpenRouter choose";
    only.setAttribute("aria-label", "OpenRouter allowed upstreams");
    onlyField.append(only);
    const ignoreField = el(documentRef, "label", "ui-field");
    ignoreField.append(el(documentRef, "span", "ui-field__label", "Never use"));
    const ignore = documentRef.createElement("input");
    ignore.type = "text";
    ignore.value = (routing.ignore || []).join(", ");
    ignore.setAttribute("aria-label", "OpenRouter blocked upstreams");
    ignoreField.append(ignore);
    const sortField = el(documentRef, "label", "ui-field");
    sortField.append(el(documentRef, "span", "ui-field__label", "Prefer by"));
    const sort = documentRef.createElement("select");
    sort.setAttribute("aria-label", "OpenRouter routing preference");
    [["", "OpenRouter default"], ["price", "Price"], ["throughput", "Throughput"], ["latency", "Latency"]].forEach(([value, label]) => {
      const option = el(documentRef, "option", "", label);
      option.value = value;
      option.selected = (routing.sort || "") === value;
      sort.append(option);
    });
    sortField.append(sort);
    routingFields.append(onlyField, ignoreField, sortField);
    const routingToggles = el(documentRef, "div", "ui-settings__media-toggles");
    const privacy = documentRef.createElement("input");
    privacy.type = "checkbox";
    privacy.checked = routing.data_collection === "deny";
    privacy.setAttribute("aria-label", "Block OpenRouter providers that retain or train on prompts");
    const privacyLabel = el(documentRef, "label", "");
    privacyLabel.append(privacy, documentRef.createTextNode(" Block providers that retain or train on prompts"));
    const pin = documentRef.createElement("input");
    pin.type = "checkbox";
    pin.checked = routing.allow_fallbacks === false;
    pin.setAttribute("aria-label", "Never fall back to another OpenRouter upstream");
    const pinLabel = el(documentRef, "label", "");
    pinLabel.append(pin, documentRef.createTextNode(" Never fall back to another upstream"));
    routingToggles.append(privacyLabel, pinLabel);
    const routingStatus = el(documentRef, "p", "ui-settings__connection-status");
    routingStatus.setAttribute("role", "status");
    const routingFooter = el(documentRef, "div", "ui-settings__connection-footer");
    const saveRouting = el(documentRef, "button", "ui-button ui-button--quiet", "Save OpenRouter routing");
    saveRouting.type = "button";
    routingFooter.append(saveRouting);
    saveRouting.addEventListener("click", async () => {
      saveRouting.disabled = true;
      routingStatus.textContent = "Saving OpenRouter routing…";
      try {
        await services.apiClient.put("/api/openrouter_routing", {
          only: splitRouting(only.value),
          ignore: splitRouting(ignore.value),
          data_collection: privacy.checked ? "deny" : "allow",
          allow_fallbacks: !pin.checked,
          sort: sort.value || null,
        }, { channel: "settings-openrouter-routing", owner: "settings-ai-connections" });
        if (saveRouting.isConnected) routingStatus.textContent = "OpenRouter routing saved.";
      } catch (error) {
        if (saveRouting.isConnected) routingStatus.textContent = error?.userMessage || error?.message || "Sonder could not save OpenRouter routing.";
      } finally {
        if (saveRouting.isConnected) saveRouting.disabled = false;
      }
    });
    openRouterGroup.append(routingCopy, routingFields, routingToggles, routingStatus, routingFooter);
  }

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
  const samplerKeys = Array.isArray(data.sampler_keys) ? data.sampler_keys : [];
  const defaultSamplers = data.default_samplers || {};
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
    const advancedRole = documentRef.createElement("details");
    advancedRole.className = "ui-settings__role-advanced";
    const roleSummary = el(documentRef, "summary", "", `Sampling and backup models for ${label}`);
    const samplerFields = el(documentRef, "div", "ui-settings__sampler-fields");
    const samplerInputs = new Map();
    samplerKeys.forEach(key => {
      const field = el(documentRef, "label", "ui-field");
      field.append(el(documentRef, "span", "ui-field__label", humanizeSettingKey(key)));
      const input = documentRef.createElement("input");
      input.type = "number";
      input.step = "any";
      input.value = String(existing[key] ?? defaultSamplers[key] ?? "");
      input.setAttribute("aria-label", `${humanizeSettingKey(key)} for ${label}`);
      field.append(input);
      samplerFields.append(field);
      samplerInputs.set(key, input);
    });
    const backupList = el(documentRef, "div", "ui-settings__backup-list");
    const backupRows = [];
    const addBackup = fallback => {
      const index = backupRows.length + 1;
      const backup = el(documentRef, "div", "ui-settings__backup-row");
      const backupProvider = documentRef.createElement("select");
      backupProvider.setAttribute("aria-label", `Backup ${index} provider for ${label}`);
      const blank = el(documentRef, "option", "", "Choose provider");
      blank.value = "";
      backupProvider.append(blank);
      providers.forEach(provider => {
        const option = el(documentRef, "option", "", provider.name || provider.kind || `Provider ${provider.id}`);
        option.value = String(provider.id);
        option.selected = String(fallback?.provider ?? "") === String(provider.id);
        backupProvider.append(option);
      });
      const backupModel = documentRef.createElement("input");
      backupModel.type = "text";
      backupModel.value = fallback?.model || "";
      backupModel.placeholder = "Backup model id";
      backupModel.setAttribute("aria-label", `Backup ${index} model for ${label}`);
      const remove = el(documentRef, "button", "ui-button ui-button--quiet", "Remove");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove backup ${index} for ${label}`);
      const record = { element: backup, provider: backupProvider, model: backupModel };
      remove.addEventListener("click", () => {
        backup.remove();
        const at = backupRows.indexOf(record);
        if (at >= 0) backupRows.splice(at, 1);
      });
      backup.append(backupProvider, backupModel, remove);
      backupRows.push(record);
      backupList.append(backup);
    };
    (Array.isArray(existing.fallbacks) ? existing.fallbacks : []).forEach(addBackup);
    const addBackupButton = el(documentRef, "button", "ui-button ui-button--quiet", "Add backup model");
    addBackupButton.type = "button";
    addBackupButton.setAttribute("aria-label", `Add backup model for ${label}`);
    addBackupButton.addEventListener("click", () => addBackup({}));
    advancedRole.append(roleSummary, samplerFields, backupList, addBackupButton);
    row.append(providerField, modelField, effortField, advancedRole);
    assignmentRows.append(row);
    roleControls.set(role, { providerSelect, modelInput, effort, samplerInputs, backupRows });
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
      for (const [key, input] of controls.samplerInputs) {
        const value = Number(input.value);
        if (input.value !== "" && Number.isFinite(value)) nextModels[role][key] = value;
        else delete nextModels[role][key];
      }
      const fallbacks = controls.backupRows.map(row => {
        const fallbackProvider = providers.find(item => String(item.id) === row.provider.value);
        return {
          provider: fallbackProvider?.id ?? row.provider.value,
          model: row.model.value.trim(),
        };
      }).filter(fallback => fallback.provider && fallback.model);
      if (fallbacks.length) nextModels[role].fallbacks = fallbacks;
      else delete nextModels[role].fallbacks;
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
  const backdropModelsId = "settings-backdrop-models";
  backdropModel.setAttribute("list", backdropModelsId);
  const backdropModels = documentRef.createElement("datalist");
  backdropModels.id = backdropModelsId;
  backdropModelField.append(backdropModel);
  backdropModelField.append(backdropModels);
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
  const discoverBackdrops = el(documentRef, "button", "ui-button ui-button--quiet", "Discover image models");
  discoverBackdrops.type = "button";
  discoverBackdrops.addEventListener("click", async () => {
    if (!backdropProvider.value) {
      backdropStatus.textContent = "Choose an image provider first.";
      backdropProvider.focus();
      return;
    }
    discoverBackdrops.disabled = true;
    backdropStatus.textContent = "Checking image models…";
    try {
      const result = await services.apiClient.get(`/api/providers/${encodeURIComponent(backdropProvider.value)}/image_models`, {
        channel: `settings-image-models:${backdropProvider.value}`, owner: "settings-backdrops",
      });
      if (!discoverBackdrops.isConnected) return;
      const models = Array.isArray(result.data?.models) ? result.data.models : [];
      backdropModels.replaceChildren();
      models.forEach(item => {
        const id = typeof item === "string" ? item : item?.id || item?.name;
        if (!id) return;
        const option = el(documentRef, "option", "", typeof item === "object" ? item.description || "" : "");
        option.value = id;
        backdropModels.append(option);
      });
      backdropStatus.textContent = models.length
        ? `${models.length} ${models.length === 1 ? "image model" : "image models"} available. Type to filter the list.`
        : "This provider returned no text-to-image models.";
    } catch (error) {
      if (discoverBackdrops.isConnected) backdropStatus.textContent = error?.userMessage || error?.message || "Sonder could not discover image models.";
    } finally {
      if (discoverBackdrops.isConnected) discoverBackdrops.disabled = false;
    }
  });
  backdropFooter.append(discoverBackdrops, saveBackdrops);
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

  section.append(head, connections, defaults, limitGroup);
  if (openRouterGroup) section.append(openRouterGroup);
  section.append(assignments, backdrops, ambience);
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
  header.append(title, settingsSearch(documentRef, services));
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
        ? advanced(documentRef, services, state, route)
        : placeholder(documentRef, active),
  );
  body.append(nav, content);
  root.append(header, body);
  services.localizer.localize(root);
  requestAnimationFrame(() => {
    nav.querySelector("[aria-current='page']")?.scrollIntoView({ block: "nearest", inline: "center" });
    const control = String(route.query?.control || "");
    if (control) {
      const target = content.querySelector(`#settings-control-${CSS.escape(control)}`);
      const focusTarget = target?.matches("button, input, select, textarea, a[href]")
        ? target
        : target?.querySelector("button, input, select, textarea, a[href]");
      focusTarget?.focus();
      target?.scrollIntoView({ block: "center" });
    }
  });
  return { element: root, teardown() {} };
}
