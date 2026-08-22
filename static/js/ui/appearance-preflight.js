"use strict";

(() => {
  const root = document.documentElement;
  const themes = new Set(["carbon-signal", "ash-brass", "midnight-ink", "parchment-night"]);
  const proseSizes = new Set(["15", "17", "19", "21"]);
  const effects = new Set(["full", "reduced", "off"]);
  const read = (key, fallback) => {
    try { return localStorage.getItem(key) || fallback; }
    catch (_) { return fallback; }
  };
  const theme = read("sonder.ui.next.theme.v1", "carbon-signal");
  const prose = read("sonder.ui.next.prose.v1", "17");
  const effect = read("sonder.ui.next.effects.v1", "full");
  root.dataset.theme = themes.has(theme) ? theme : "carbon-signal";
  root.dataset.proseSize = proseSizes.has(prose) ? prose : "17";
  root.dataset.effects = effects.has(effect) ? effect : "full";
  const systemReducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  root.dataset.motionPreference = systemReducedMotion ? "reduced" : root.dataset.effects;
  root.dataset.systemReducedMotion = String(systemReducedMotion);
  root.style.colorScheme = "dark";
})();
