"use strict";

// Appearance is intentionally browser-local. A theme changes how this device
// presents Sonder Engine without mutating a story export or affecting guests.
(() => {
  const THEME_KEY = "sonder.ui.theme";
  const PROSE_SIZE_KEY = "sonder.ui.proseSize";
  const DEFAULT_THEME = "sonder";
  const DEFAULT_PROSE_SIZE = "17";

  const themes = [
    {
      id: "sonder",
      name: "Sonder",
      description: "The current cool, atmospheric dark interface.",
      swatches: ["#121722", "#222b3d", "#79a9ff", "#9c7cff"],
      mode: "dark",
    },
    {
      id: "tavern",
      name: "Tavern",
      description: "A lit interior: visible wood grain, hearth-glow, and brass fittings.",
      swatches: ["#2b1c11", "#4d341f", "#e0a44f", "#b85f36"],
      mode: "dark",
    },
    {
      id: "lcars",
      name: "LCARS",
      description: "Flat colour blocks on black, elbow frame, pill controls.",
      swatches: ["#000000", "#99f", "#f90", "#c9c"],
      mode: "dark",
    },
    {
      id: "stone",
      name: "Stone",
      description: "Quarried granite — cut edges, mortar joints, and one torch.",
      swatches: ["#2b3033", "#464d51", "#d0ae6f", "#8c999b"],
      mode: "dark",
    },
    {
      id: "ink",
      name: "Ink",
      description: "Minimal near-black chrome with a crisp white-blue accent.",
      swatches: ["#050607", "#14171a", "#d9e6f2", "#7fa6c9"],
      mode: "dark",
    },
  ];

  const validThemeIds = new Set(themes.map(theme => theme.id));
  const validProseSizes = new Set(["15", "17", "19", "21"]);

  function readStored(key, fallback) {
    try {
      return localStorage.getItem(key) || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeStored(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      // Private browsing and hardened browser profiles may block storage.
      // The live appearance still applies for the current page.
    }
  }

  function normaliseTheme(id) {
    return validThemeIds.has(id) ? id : DEFAULT_THEME;
  }

  function normaliseProseSize(size) {
    const value = String(size || "");
    return validProseSizes.has(value) ? value : DEFAULT_PROSE_SIZE;
  }

  function applyTheme(id, options = {}) {
    const themeId = normaliseTheme(id);
    const theme = themes.find(item => item.id === themeId) || themes[0];
    const root = document.documentElement;
    root.dataset.theme = themeId;
    root.style.colorScheme = theme.mode;
    if (document.body) document.body.dataset.theme = themeId;
    if (options.persist !== false) writeStored(THEME_KEY, themeId);
    window.dispatchEvent(new CustomEvent("sonder-theme-change", {
      detail: { theme: themeId },
    }));
    return themeId;
  }

  function applyProseSize(size, options = {}) {
    const proseSize = normaliseProseSize(size);
    document.documentElement.dataset.proseSize = proseSize;
    if (options.persist !== false) writeStored(PROSE_SIZE_KEY, proseSize);
    window.dispatchEvent(new CustomEvent("sonder-prose-size-change", {
      detail: { size: proseSize },
    }));
    return proseSize;
  }

  window.SONDER_APPEARANCE = {
    THEME_KEY,
    PROSE_SIZE_KEY,
    DEFAULT_THEME,
    DEFAULT_PROSE_SIZE,
    themes,
    applyTheme,
    applyProseSize,
    currentTheme: () => normaliseTheme(document.documentElement.dataset.theme),
    currentProseSize: () => normaliseProseSize(document.documentElement.dataset.proseSize),
  };

  // Run before the stylesheet is parsed to prevent a light/dark flash.
  applyTheme(readStored(THEME_KEY, DEFAULT_THEME), { persist: false });
  applyProseSize(readStored(PROSE_SIZE_KEY, DEFAULT_PROSE_SIZE), { persist: false });

  // `page-hidden` on <body>: the CSS hook for "nobody is looking at this".
  // There is no selector for `document.hidden`, and purely decorative
  // infinite animations (the tavern hearth in themes.css) should not run
  // against a tab that is not on screen -- browsers throttle them, but
  // throttled is not stopped, and a full-viewport composited layer keeps the
  // GPU awake either way. Lives here rather than app.js so every page that
  // loads a theme gets it (guest and login load themes.css too). This script
  // runs in <head>, before <body> exists, so the initial state is stamped on
  // DOMContentLoaded rather than immediately.
  function syncPageHidden() {
    if (document.body) document.body.classList.toggle("page-hidden", document.hidden);
  }
  document.addEventListener("visibilitychange", syncPageHidden);
  document.addEventListener("DOMContentLoaded", syncPageHidden);
})();
