export const CUSTOM_THEME_STORAGE_KEY = "sonder.ui.next.custom-theme.v1";
export const CUSTOM_THEME_SCHEMA_VERSION = 1;

export const CUSTOM_THEME_ROLES = Object.freeze([
  Object.freeze({ id: "background", label: "Background", property: "--ui-custom-background" }),
  Object.freeze({ id: "panel", label: "Panel", property: "--ui-custom-panel" }),
  Object.freeze({ id: "text", label: "Primary text", property: "--ui-custom-text" }),
  Object.freeze({ id: "muted", label: "Muted text", property: "--ui-custom-muted" }),
  Object.freeze({ id: "accent", label: "Accent", property: "--ui-custom-accent" }),
  Object.freeze({ id: "attention", label: "Attention", property: "--ui-custom-attention" }),
  Object.freeze({ id: "success", label: "Success", property: "--ui-custom-success" }),
  Object.freeze({ id: "danger", label: "Danger", property: "--ui-custom-danger" }),
]);

export const DEFAULT_CUSTOM_THEME = Object.freeze({
  background: "#090D10",
  panel: "#141B20",
  text: "#EEF3F2",
  muted: "#AEB9B7",
  accent: "#80E4E8",
  attention: "#D0A75B",
  success: "#76C29A",
  danger: "#DC747D",
});

const ROLE_IDS = Object.freeze(CUSTOM_THEME_ROLES.map(role => role.id));
const ROLE_SET = new Set(ROLE_IDS);

export function normalizeHex(value) {
  const source = String(value ?? "").trim();
  const short = /^#([0-9a-f]{3})$/i.exec(source);
  if (short) {
    return `#${[...short[1]].map(character => character.repeat(2)).join("")}`.toUpperCase();
  }
  if (!/^#[0-9a-f]{6}$/i.test(source)) {
    throw new TypeError("Colors must use #RRGGBB hexadecimal notation.");
  }
  return source.toUpperCase();
}

export function hexToRgb(value) {
  const hex = normalizeHex(value).slice(1);
  return Object.freeze({
    red: Number.parseInt(hex.slice(0, 2), 16),
    green: Number.parseInt(hex.slice(2, 4), 16),
    blue: Number.parseInt(hex.slice(4, 6), 16),
  });
}

export function rgbToHex(value) {
  const channels = [value?.red, value?.green, value?.blue].map(channel => Number(channel));
  if (channels.some(channel => !Number.isInteger(channel) || channel < 0 || channel > 255)) {
    throw new TypeError("RGB channels must be whole numbers from 0 through 255.");
  }
  return `#${channels.map(channel => channel.toString(16).padStart(2, "0")).join("")}`.toUpperCase();
}

function luminance(value) {
  const channels = Object.values(hexToRgb(value)).map(channel => {
    const surface = channel / 255;
    return surface <= 0.04045 ? surface / 12.92 : ((surface + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrastRatio(first, second) {
  const light = luminance(first);
  const dark = luminance(second);
  return (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05);
}

function normalizePalette(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("A custom theme must contain eight semantic colors.");
  }
  const keys = Object.keys(value);
  if (keys.length !== ROLE_IDS.length || keys.some(key => !ROLE_SET.has(key))) {
    throw new TypeError("A custom theme must contain exactly the eight recognized color roles.");
  }
  return Object.fromEntries(ROLE_IDS.map(id => [id, normalizeHex(value[id])]));
}

function contrastError(errors, palette, foreground, background, minimum, foregroundLabel, backgroundLabel) {
  const ratio = contrastRatio(palette[foreground], palette[background]);
  if (ratio + Number.EPSILON < minimum) {
    errors.push(`${foregroundLabel} must reach ${minimum}:1 against ${backgroundLabel}.`);
  }
}

export function validateCustomTheme(value) {
  let palette;
  try {
    palette = normalizePalette(value);
  } catch (error) {
    return Object.freeze({ valid: false, palette: null, errors: Object.freeze([error.message]) });
  }
  const errors = [];
  contrastError(errors, palette, "text", "background", 4.5, "Primary text", "Background");
  contrastError(errors, palette, "text", "panel", 4.5, "Primary text", "Panel");
  contrastError(errors, palette, "muted", "background", 4.5, "Muted text", "Background");
  contrastError(errors, palette, "muted", "panel", 4.5, "Muted text", "Panel");
  for (const [id, label] of [
    ["accent", "Accent"],
    ["attention", "Attention"],
    ["success", "Success"],
    ["danger", "Danger"],
  ]) {
    contrastError(errors, palette, id, "background", 3, label, "Background");
    contrastError(errors, palette, id, "panel", 3, label, "Panel");
  }
  if (contrastRatio(palette.background, palette.panel) < 1.12) {
    errors.push("Background and Panel must remain visibly distinct.");
  }
  return Object.freeze({
    valid: errors.length === 0,
    palette: Object.freeze(palette),
    errors: Object.freeze(errors),
  });
}

export function parseCustomTheme(value) {
  let parsed;
  try {
    parsed = typeof value === "string" ? JSON.parse(value) : value;
  } catch {
    throw new TypeError("Custom theme JSON could not be read.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new TypeError("Custom theme JSON must be an object.");
  }
  const keys = Object.keys(parsed);
  if (keys.length !== 2 || !keys.includes("version") || !keys.includes("colors")) {
    throw new TypeError("Custom theme JSON contains unsupported fields.");
  }
  if (parsed.version !== CUSTOM_THEME_SCHEMA_VERSION) {
    throw new TypeError("Custom theme JSON uses an unsupported version.");
  }
  const validation = validateCustomTheme(parsed.colors);
  if (!validation.valid) throw new TypeError(validation.errors.join(" "));
  return validation.palette;
}

export function serializeCustomTheme(value) {
  const validation = validateCustomTheme(value);
  if (!validation.valid) throw new TypeError(validation.errors.join(" "));
  return JSON.stringify({
    version: CUSTOM_THEME_SCHEMA_VERSION,
    colors: validation.palette,
  }, null, 2);
}

export function applyCustomTheme(root, value) {
  if (!root?.style?.setProperty) throw new TypeError("A style-bearing root is required.");
  const validation = validateCustomTheme(value);
  if (!validation.valid) throw new TypeError(validation.errors.join(" "));
  for (const role of CUSTOM_THEME_ROLES) {
    root.style.setProperty(role.property, validation.palette[role.id]);
  }
  return validation.palette;
}

export function readCustomTheme(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem?.(CUSTOM_THEME_STORAGE_KEY);
    return raw ? parseCustomTheme(raw) : DEFAULT_CUSTOM_THEME;
  } catch {
    return DEFAULT_CUSTOM_THEME;
  }
}

export function persistCustomTheme(value, storage = globalThis.localStorage) {
  const serialized = serializeCustomTheme(value);
  storage?.setItem?.(CUSTOM_THEME_STORAGE_KEY, serialized);
  return parseCustomTheme(serialized);
}
