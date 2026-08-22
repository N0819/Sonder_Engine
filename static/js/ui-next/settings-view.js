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
