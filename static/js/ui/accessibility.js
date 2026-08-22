const STORAGE_KEY = "sonder.ui.next.accessibility.v1";

export const accessibilityDefaults = Object.freeze({
  mode: false,
  solidSurfaces: false,
  highContrast: false,
  strongFocus: false,
  reducedMotion: false,
  largeUi: false,
  largeProse: false,
  roomyTargets: false,
  statusMarkers: false,
});

const attributes = Object.freeze({
  solidSurfaces: "a11ySolid",
  highContrast: "a11yHighContrast",
  strongFocus: "a11yStrongFocus",
  reducedMotion: "a11yReducedMotion",
  largeUi: "a11yLargeUi",
  largeProse: "a11yLargeProse",
  roomyTargets: "a11yRoomyTargets",
  statusMarkers: "a11yStatusMarkers",
});

function readPreferences() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return Object.fromEntries(Object.entries(accessibilityDefaults).map(([key, fallback]) => [key, typeof parsed[key] === "boolean" ? parsed[key] : fallback]));
  } catch (_) {
    return { ...accessibilityDefaults };
  }
}

function writePreferences(preferences) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences)); }
  catch (_) { /* The live preference still applies. */ }
}

export function applyAccessibility(preferences) {
  const normalized = { ...accessibilityDefaults, ...preferences };
  const root = document.documentElement;
  for (const [key, attribute] of Object.entries(attributes)) {
    root.dataset[attribute] = String(Boolean(normalized[key]));
  }
  document.dispatchEvent(new CustomEvent("ui:accessibility-change", { detail: { ...normalized } }));
  return normalized;
}

export function updateAccessibility(patch, { persist = true } = {}) {
  let next = { ...readPreferences(), ...patch };
  if (Object.hasOwn(patch, "mode") && patch.mode) {
    next = Object.fromEntries(Object.keys(accessibilityDefaults).map((key) => [key, true]));
  } else if (Object.hasOwn(patch, "mode") && !patch.mode) {
    next.mode = false;
  } else {
    next.mode = Object.keys(attributes).every((key) => Boolean(next[key]));
  }
  if (persist) writePreferences(next);
  return applyAccessibility(next);
}

export function initAccessibility() {
  return applyAccessibility(readPreferences());
}
