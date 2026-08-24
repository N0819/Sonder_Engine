const SPRITE = "/static/assets/icons/sonder-icons.svg?release=alpha98-ui5-7fa758fa6df7";
const ICON_NAMES = new Set([
  "play", "library", "settings", "tools", "cast", "world", "style", "dialogue", "clothing", "image", "ambience",
  "send", "stop", "search", "filter", "close", "more", "menu", "chevron-left", "chevron-right", "chevron-down",
  "plus", "minus", "import", "export", "edit", "delete", "duplicate", "archive", "favorite", "recent", "story",
  "character", "persona", "lore", "link", "unlink", "pin", "resize", "theme", "api", "update", "prompt",
  "extension", "sound-on", "sound-off", "retry", "tasks", "check", "warning", "error", "info", "lock", "unlock",
  "home", "folder", "calendar", "connection", "offline", "spark", "sort", "save",
]);

function assertName(name) {
  if (!ICON_NAMES.has(name)) throw new RangeError(`Unknown Sonder icon: ${name}`);
}

export function createIcon(name, { size = "default", label = "" } = {}) {
  assertName(name);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("ui-icon");
  if (size === "small") svg.classList.add("ui-icon--small");
  if (size === "large") svg.classList.add("ui-icon--large");
  svg.setAttribute("focusable", "false");
  if (label) {
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", label);
  } else {
    svg.setAttribute("aria-hidden", "true");
  }
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `${SPRITE}#icon-${name}`);
  svg.append(use);
  return svg;
}

export function createIconLabel(name, text, options = {}) {
  const wrapper = document.createElement("span");
  wrapper.className = "ui-icon-label";
  wrapper.append(createIcon(name, options));
  const copy = document.createElement("span");
  copy.textContent = text;
  wrapper.append(copy);
  return wrapper;
}

export function setIconButton(button, name, { accessibleName, tooltip = accessibleName } = {}) {
  if (!(button instanceof HTMLButtonElement)) throw new TypeError("An HTML button is required.");
  if (!accessibleName) throw new TypeError("Icon-only buttons require an accessibleName.");
  button.replaceChildren(createIcon(name));
  button.classList.add("ui-button", "ui-button--icon");
  button.setAttribute("aria-label", accessibleName);
  if (tooltip) button.title = tooltip;
  return button;
}

export const iconNames = Object.freeze([...ICON_NAMES]);
