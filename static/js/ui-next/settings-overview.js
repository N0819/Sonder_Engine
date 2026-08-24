export const MODULE_RELEASE = "alpha98-ui14-8c5f0c3f2d06";

export const SETTINGS_NAVIGATION_GROUPS = Object.freeze([
  Object.freeze({
    id: "account-access",
    label: "Account and access",
    rows: Object.freeze([
      Object.freeze({ id: "ai-connections", label: "Provider credentials", icon: "api", href: "#/settings/ai-connections" }),
    ]),
  }),
  Object.freeze({
    id: "ai-models",
    label: "AI and models",
    rows: Object.freeze([
      Object.freeze({ id: "model-assignments", label: "Model assignments", icon: "connection", href: "#/settings/ai-connections?control=models" }),
    ]),
  }),
  Object.freeze({
    id: "appearance-accessibility",
    label: "Appearance and accessibility",
    rows: Object.freeze([
      Object.freeze({ id: "theme", label: "Theme", icon: "theme", href: "#/settings/experience?control=themes" }),
      Object.freeze({ id: "reading", label: "Reading & layout", icon: "style", href: "#/settings/experience?control=reading" }),
      Object.freeze({ id: "sound", label: "Sound & motion", icon: "sound-on", href: "#/settings/experience?control=sound" }),
      Object.freeze({ id: "accessibility", label: "Accessibility", icon: "check", href: "#/settings/experience?control=accessibility" }),
    ]),
  }),
  Object.freeze({
    id: "story-content",
    label: "Story defaults and content",
    rows: Object.freeze([
      Object.freeze({ id: "content", label: "Content", icon: "prompt", href: "#/settings/content" }),
    ]),
  }),
  Object.freeze({
    id: "data-extensions-maintenance",
    label: "Data, extensions, and maintenance",
    rows: Object.freeze([
      Object.freeze({ id: "add-ons", label: "Add-ons", icon: "extension", href: "#/settings/add-ons" }),
      Object.freeze({ id: "maintenance", label: "Maintenance", icon: "maintenance", href: "#/settings/maintenance" }),
    ]),
  }),
  Object.freeze({
    id: "advanced",
    label: "Advanced",
    rows: Object.freeze([
      Object.freeze({ id: "prompt-editor", label: "Prompt editor", icon: "prompt", href: "#/settings/advanced?tool=prompts" }),
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
    "model-assignments": defaultModel ? `Default · ${defaultModel}` : "Choose defaults and specialist models",
    "prompt-editor": "Advanced prompt templates and presets",
    "raw-story-data": input?.storyOpen ? "Inspect the current Story world record" : "Open a Story first",
  });
}

export function projectSettingsNavigation(input = {}) {
  const summaries = summaryProjection(input);
  return Object.freeze(SETTINGS_NAVIGATION_GROUPS.map(group => Object.freeze({
    ...group,
    rows: Object.freeze(group.rows.map(row => Object.freeze({
      ...row,
      summary: summaries[row.id] || "",
      available: true,
    }))),
  })));
}
