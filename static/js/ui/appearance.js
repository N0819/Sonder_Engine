import {
  applyCustomTheme,
  CUSTOM_THEME_STORAGE_KEY,
  persistCustomTheme,
  readCustomTheme,
} from "./custom-theme.js?release=alpha98-ui14-8c5f0c3f2d06";

const THEMES = Object.freeze([
  { id: "carbon-signal", name: "Carbon Signal" },
  { id: "ash-brass", name: "Ash and Brass" },
  { id: "midnight-ink", name: "Midnight Ink" },
  { id: "parchment-night", name: "Parchment Night" },
  { id: "neon-circuit", name: "Neon Circuit" },
  { id: "modern-slate", name: "Modern Slate" },
  { id: "custom", name: "Custom Theme" },
]);
const themeIds = new Set(THEMES.map(({ id }) => id));
const proseSizes = new Set(["15", "17", "19", "21"]);
const effectLevels = new Set(["full", "reduced", "off"]);

function store(key, value) {
  try { localStorage.setItem(key, value); }
  catch (_) { /* Preferences remain active for this page. */ }
}

function applyDataset(name, value, allowed, fallback, key, persist) {
  const next = allowed.has(String(value)) ? String(value) : fallback;
  document.documentElement.dataset[name] = next;
  if (persist) store(key, next);
  document.dispatchEvent(new CustomEvent("ui:appearance-change", {
    detail: { name, value: next },
  }));
  return next;
}

export const appearance = Object.freeze({
  themes: THEMES,
  setTheme: (value, persist = true) => {
    if (value === "custom") applyCustomTheme(document.documentElement, readCustomTheme());
    return applyDataset("theme", value, themeIds, "carbon-signal", "sonder.ui.next.theme.v1", persist);
  },
  getCustomTheme: () => readCustomTheme(),
  setCustomTheme: (value, persist = true) => {
    const palette = persist
      ? persistCustomTheme(value)
      : applyCustomTheme(document.documentElement, value);
    applyCustomTheme(document.documentElement, palette);
    applyDataset("theme", "custom", themeIds, "carbon-signal", "sonder.ui.next.theme.v1", persist);
    return palette;
  },
  customThemeStorageKey: CUSTOM_THEME_STORAGE_KEY,
  setProseSize: (value, persist = true) => applyDataset("proseSize", value, proseSizes, "17", "sonder.ui.next.prose.v1", persist),
  setEffects: (value, persist = true) => {
    const next = applyDataset("effects", value, effectLevels, "full", "sonder.ui.next.effects.v1", persist);
    const systemReduced = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    document.documentElement.dataset.motionPreference = systemReduced ? "reduced" : next;
    return next;
  },
});
