export const MODULE_RELEASE = "alpha98-ui10-c14a4cf8dabd";

export const SETTINGS_OVERVIEW_GROUPS = Object.freeze([
  Object.freeze({
    id: "connections",
    label: "Connections",
    rows: Object.freeze([
      Object.freeze({ id: "ai-connections", label: "AI Connections", icon: "api", href: "#/settings/ai-connections" }),
    ]),
  }),
  Object.freeze({
    id: "appearance",
    label: "Appearance",
    rows: Object.freeze([
      Object.freeze({ id: "theme", label: "Theme", icon: "theme", href: "#/settings/experience?control=themes" }),
      Object.freeze({ id: "reading", label: "Reading & layout", icon: "style", href: "#/settings/experience?control=reading" }),
      Object.freeze({ id: "sound", label: "Sound & motion", icon: "sound-on", href: "#/settings/experience?control=sound" }),
      Object.freeze({ id: "accessibility", label: "Accessibility", icon: "check", href: "#/settings/experience?control=accessibility" }),
    ]),
  }),
  Object.freeze({
    id: "story-host",
    label: "Story & host",
    rows: Object.freeze([
      Object.freeze({ id: "content", label: "Content", icon: "prompt", href: "#/settings/content" }),
      Object.freeze({ id: "add-ons", label: "Add-ons", icon: "extension", href: "#/settings/add-ons" }),
      Object.freeze({ id: "maintenance", label: "Maintenance", icon: "maintenance", href: "#/settings/maintenance" }),
      Object.freeze({ id: "story-imports", label: "Story imports & backups", icon: "import", href: "#/library/stories" }),
    ]),
  }),
  Object.freeze({
    id: "advanced",
    label: "Advanced",
    rows: Object.freeze([
      Object.freeze({ id: "model-assignments", label: "Model assignments", icon: "connection", href: "#/settings/ai-connections?control=models" }),
      Object.freeze({ id: "prompt-editor", label: "Prompt editor", icon: "prompt", href: "#/settings/advanced?tool=prompts" }),
      Object.freeze({ id: "turn-details", label: "Turn details", icon: "terminal", href: "#/play/story-tools?tool=turn-details" }),
      Object.freeze({ id: "raw-story-data", label: "Raw story data", icon: "world", href: "#/settings/advanced?tool=story-data" }),
    ]),
  }),
]);

const THEME_NAMES = Object.freeze({
  "carbon-signal": "Carbon Signal",
  "ash-brass": "Ash and Brass",
  "midnight-ink": "Midnight Ink",
  "parchment-night": "Parchment Night",
  "neon-circuit": "Neon Circuit",
  "modern-slate": "Modern Slate",
  custom: "Custom Theme",
});

const PROSE_NAMES = Object.freeze({
  15: "Small",
  17: "Standard",
  19: "Large",
  21: "Extra large",
});

const EFFECT_NAMES = Object.freeze({
  full: "Full effects",
  reduced: "Reduced effects",
  off: "Effects off",
});

const ACCESSIBILITY_OVERRIDES = Object.freeze([
  "solidSurfaces",
  "highContrast",
  "strongFocus",
  "reducedMotion",
  "largeUi",
  "largeProse",
  "roomyTargets",
]);

function plural(count, singular, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

function summaryProjection(input) {
  const appearance = input?.appearance || {};
  const settings = input?.settings || {};
  const atmosphere = input?.atmosphere || {};
  const accessibility = input?.accessibility || {};
  const extensions = input?.extensions || {};
  const providers = Array.isArray(settings.providers) ? settings.providers : null;
  const defaultModel = String(settings.agent_models?.default?.model || "").trim();
  const theme = String(input?.theme || appearance.theme || "carbon-signal");
  const prose = String(input?.proseSize || appearance.proseSize || "17");
  const density = String(input?.density || appearance.density || "comfortable");
  const effects = String(input?.effects || appearance.effects || "full");
  const overrideCount = ACCESSIBILITY_OVERRIDES.filter(key => accessibility[key]).length;
  const installed = extensions.status === "ready" && Array.isArray(extensions.items)
    ? extensions.items : null;
  const enabled = installed?.filter(extension => extension?.enabled).length || 0;

  return Object.freeze({
    "ai-connections": providers
      ? `${plural(providers.length, "provider")} · ${defaultModel || "No default model"}`
      : "Providers, credentials, and model routing",
    theme: THEME_NAMES[theme] || "Carbon Signal",
    reading: `${PROSE_NAMES[prose] || "Standard"} · ${density === "compact" ? "Compact" : "Comfortable"}`,
    sound: `${EFFECT_NAMES[effects] || "Full effects"} · ${atmosphere.muted ? "Sound muted" : "Sound on"}`,
    accessibility: accessibility.mode
      ? "Accessibility Mode"
      : (overrideCount ? plural(overrideCount, "accessibility override") : "Standard"),
    content: "Story boundaries, narrator voice, and living-world ceilings",
    "add-ons": installed
      ? `${enabled} enabled · ${installed.length} installed`
      : "Extensions, permissions, updates, and recovery",
    maintenance: "Updates, storage conversion, memory search, and diagnostics",
    "story-imports": "Opens Library for import, portable export, and deletion",
    "model-assignments": defaultModel ? `Default · ${defaultModel}` : "Choose defaults and specialist models",
    "prompt-editor": "Advanced prompt templates and presets",
    "turn-details": input?.storyOpen ? "Inspect the current Story turn" : "Open a Story first",
    "raw-story-data": input?.storyOpen ? "Inspect the current Story world record" : "Open a Story first",
  });
}

export function projectSettingsOverview(input = {}) {
  const summaries = summaryProjection(input);
  return Object.freeze(SETTINGS_OVERVIEW_GROUPS.map(group => Object.freeze({
    ...group,
    rows: Object.freeze(group.rows.map(row => Object.freeze({
      ...row,
      summary: summaries[row.id] || "",
      available: row.id !== "turn-details" || Boolean(input.storyOpen),
    }))),
  })));
}

function node(documentRef, tag, className = "", text = "") {
  const element = documentRef.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

export function renderSettingsOverview(options = {}) {
  const { document: documentRef, groups, iconFactory, navigate, rememberFocus } = options;
  const overview = node(documentRef, "section", "ui-settings__overview");
  overview.setAttribute("aria-label", "Settings overview");

  for (const group of groups) {
    const section = node(documentRef, "section", "ui-settings__overview-group");
    section.dataset.settingsOverviewGroup = group.id;
    const heading = node(documentRef, "h2", "ui-settings__overview-heading", group.label);
    heading.id = `settings-overview-${group.id}`;
    const ledger = node(documentRef, "div", "ui-settings__overview-ledger");
    ledger.setAttribute("aria-labelledby", heading.id);

    for (const row of group.rows) {
      const control = node(
        documentRef,
        row.available ? "a" : "div",
        `ui-settings__overview-row${row.available ? "" : " ui-settings__overview-row--unavailable"}`,
      );
      control.dataset.settingsOverviewRow = row.id;
      const summaryId = `settings-overview-${row.id}-summary`;
      if (row.available) {
        control.href = row.href;
        control.dataset.focusIdentity = `settings-overview:${row.id}`;
        control.addEventListener("click", event => {
          event.preventDefault();
          navigate?.(row.href);
          rememberFocus?.(control.dataset.focusIdentity);
        });
      } else {
        control.setAttribute("aria-disabled", "true");
      }
      control.setAttribute("aria-describedby", summaryId);
      const title = node(documentRef, "span", "ui-settings__overview-title", row.label);
      const summary = node(documentRef, "span", "ui-settings__overview-summary", row.summary);
      summary.id = summaryId;
      control.append(
        iconFactory(row.icon),
        title,
        summary,
        iconFactory("chevron-right"),
      );
      ledger.append(control);
    }
    section.append(heading, ledger);
    overview.append(section);
  }
  return overview;
}
