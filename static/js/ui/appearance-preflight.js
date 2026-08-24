"use strict";

(() => {
  const root = document.documentElement;
  const themes = new Set(["carbon-signal", "ash-brass", "midnight-ink", "parchment-night", "neon-circuit", "modern-slate", "custom"]);
  const customRoles = Object.freeze([
    ["background", "--ui-custom-background"],
    ["panel", "--ui-custom-panel"],
    ["text", "--ui-custom-text"],
    ["muted", "--ui-custom-muted"],
    ["accent", "--ui-custom-accent"],
    ["attention", "--ui-custom-attention"],
    ["success", "--ui-custom-success"],
    ["danger", "--ui-custom-danger"],
  ]);
  const customDefaults = Object.freeze({
    background: "#090D10", panel: "#141B20", text: "#EEF3F2", muted: "#AEB9B7",
    accent: "#80E4E8", attention: "#D0A75B", success: "#76C29A", danger: "#DC747D",
  });
  const rgb = value => [
    Number.parseInt(value.slice(1, 3), 16),
    Number.parseInt(value.slice(3, 5), 16),
    Number.parseInt(value.slice(5, 7), 16),
  ];
  const luminance = value => {
    const channels = rgb(value).map(channel => {
      const surface = channel / 255;
      return surface <= 0.04045 ? surface / 12.92 : ((surface + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  };
  const contrast = (first, second) => {
    const firstLight = luminance(first);
    const secondLight = luminance(second);
    return (Math.max(firstLight, secondLight) + 0.05) / (Math.min(firstLight, secondLight) + 0.05);
  };
  const customContrastIsValid = colors => [
    ["text", "background", 4.5], ["text", "panel", 4.5],
    ["muted", "background", 4.5], ["muted", "panel", 4.5],
    ["accent", "background", 3], ["accent", "panel", 3],
    ["attention", "background", 3], ["attention", "panel", 3],
    ["success", "background", 3], ["success", "panel", 3],
    ["danger", "background", 3], ["danger", "panel", 3],
  ].every(([foreground, background, minimum]) => contrast(colors[foreground], colors[background]) >= minimum)
    && contrast(colors.background, colors.panel) >= 1.12;
  const proseSizes = new Set(["15", "17", "19", "21"]);
  const effects = new Set(["full", "reduced", "off"]);
  const read = (key, fallback) => {
    try { return localStorage.getItem(key) || fallback; }
    catch (_) { return fallback; }
  };
  const theme = read("sonder.ui.next.theme.v1", "carbon-signal");
  const prose = read("sonder.ui.next.prose.v1", "17");
  const effect = read("sonder.ui.next.effects.v1", "full");
  const selectedTheme = themes.has(theme) ? theme : "carbon-signal";
  if (selectedTheme === "custom") {
    let colors = customDefaults;
    try {
      const parsed = JSON.parse(read("sonder.ui.next.custom-theme.v1", "{}"));
      const keys = Object.keys(parsed?.colors || {});
      const validKeys = keys.length === customRoles.length
        && keys.every(key => customRoles.some(([role]) => role === key));
      const validColors = customRoles.every(([role]) => /^#[0-9a-f]{6}$/i.test(parsed?.colors?.[role] || ""));
      if (parsed?.version === 1 && validKeys && validColors && customContrastIsValid(parsed.colors)) {
        colors = Object.fromEntries(customRoles.map(([role]) => [role, parsed.colors[role].toUpperCase()]));
      }
    } catch (_) { /* Shipped custom defaults remain authoritative. */ }
    customRoles.forEach(([role, property]) => root.style.setProperty(property, colors[role]));
  }
  root.dataset.theme = selectedTheme;
  root.dataset.proseSize = proseSizes.has(prose) ? prose : "17";
  root.dataset.effects = effects.has(effect) ? effect : "full";
  const systemReducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  root.dataset.motionPreference = systemReducedMotion ? "reduced" : root.dataset.effects;
  root.dataset.systemReducedMotion = String(systemReducedMotion);
  root.style.colorScheme = "dark";
})();
