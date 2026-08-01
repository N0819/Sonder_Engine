"use strict";

// Appearance is intentionally browser-local. A theme changes how this device
// presents Sonder Engine without mutating a story export or affecting guests.
(() => {
  const THEME_KEY = "sonder.ui.theme";
  const PROSE_SIZE_KEY = "sonder.ui.proseSize";
  const EFFECTS_KEY = "sonder.ui.effects";
  const DEFAULT_THEME = "sonder";
  const DEFAULT_PROSE_SIZE = "17";
  const DEFAULT_EFFECTS = "full";

  // How much of the decorative layer runs. This is a POWER control, not a
  // taste one, which is why it is worth its own setting: falling weather, the
  // tavern hearth and the backdrop crossfade are composited full-viewport
  // layers, and a composited animation is cheap for the main thread but not
  // free for the machine -- it keeps the browser's compositor AND (on Wayland)
  // the system compositor awake at the panel's refresh rate for as long as it
  // runs. On a 1440p laptop panel that is 221 million pixels a second, on
  // battery, to make rain fall behind text.
  //
  //   full     everything animates (the default; unchanged behaviour)
  //   reduced  everything still DRAWS, nothing moves -- weather hangs, the
  //            hearth holds one brightness, backdrops cut instead of dissolve
  //   off      the decorative overlays are not drawn at all
  //
  // Backdrops themselves survive every level: the photograph of the room is
  // content, not an effect. `off` removes the weather layer and the hearth,
  // which are the two things that animate forever.
  const effectsLevels = [
    { id: "full", name: "Full", description: "Weather falls, the hearth flickers, backdrops dissolve." },
    { id: "reduced", name: "Reduced", description: "Everything still drawn, nothing animates. Much lighter on battery." },
    { id: "off", name: "Off", description: "No weather and no hearth glow. Backdrops still shown." },
  ];
  const validEffects = new Set(effectsLevels.map(level => level.id));

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

  function normaliseEffects(level) {
    const value = String(level || "");
    return validEffects.has(value) ? value : DEFAULT_EFFECTS;
  }

  function applyEffects(level, options = {}) {
    const effects = normaliseEffects(level);
    document.documentElement.dataset.effects = effects;
    if (options.persist !== false) writeStored(EFFECTS_KEY, effects);
    // weather-fx listens for this: CSS can stop an animation, but only JS can
    // avoid building the layers and generating their tiles in the first place.
    window.dispatchEvent(new CustomEvent("sonder-effects-change", {
      detail: { effects },
    }));
    return effects;
  }

  window.SONDER_APPEARANCE = {
    THEME_KEY,
    PROSE_SIZE_KEY,
    EFFECTS_KEY,
    DEFAULT_THEME,
    DEFAULT_PROSE_SIZE,
    DEFAULT_EFFECTS,
    themes,
    effectsLevels,
    applyTheme,
    applyProseSize,
    applyEffects,
    currentTheme: () => normaliseTheme(document.documentElement.dataset.theme),
    currentProseSize: () => normaliseProseSize(document.documentElement.dataset.proseSize),
    currentEffects: () => normaliseEffects(document.documentElement.dataset.effects),
  };

  // Run before the stylesheet is parsed to prevent a light/dark flash.
  applyTheme(readStored(THEME_KEY, DEFAULT_THEME), { persist: false });
  applyProseSize(readStored(PROSE_SIZE_KEY, DEFAULT_PROSE_SIZE), { persist: false });
  applyEffects(readStored(EFFECTS_KEY, DEFAULT_EFFECTS), { persist: false });

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
