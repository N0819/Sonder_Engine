export const MODULE_RELEASE = "alpha98-ui9-ff279a1d1d7f";

const OWNER = /^[a-z][a-z0-9_-]{1,63}$/;
const ID = /^[A-Za-z0-9:._-]{1,120}$/;
const COMBO = /^(?:mod\+)?(?:[a-z0-9]|,|\/|escape)$/;

export class ShortcutCollisionError extends Error {
  constructor(combo, owner) {
    super(`Shortcut collision for ${combo}; it is already owned by ${owner}.`);
    this.name = "ShortcutCollisionError";
    this.kind = "shortcut-collision";
    this.combo = combo;
    this.owner = owner;
  }
}

function normalizeCombo(value) {
  const combo = String(value || "").trim().toLowerCase();
  if (!COMBO.test(combo)) throw new TypeError(`Invalid shortcut: ${combo}`);
  return combo;
}

function eventCombo(event) {
  const key = String(event.key || "").toLowerCase();
  const normalizedKey = key === "esc" ? "escape" : key;
  if (event.metaKey || event.ctrlKey) return `mod+${normalizedKey}`;
  if (event.altKey) return "";
  return normalizedKey;
}

function isTypingTarget(target) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])"));
}

export function createShortcutRegistry(options = {}) {
  const target = options.target || window;
  const registrations = new Map();
  let started = false;

  const register = definition => {
    const owner = String(definition?.owner || "");
    const id = String(definition?.id || "");
    const combo = normalizeCombo(definition?.combo);
    if (!OWNER.test(owner) || !ID.test(id) || typeof definition?.handler !== "function") {
      throw new TypeError("A shortcut requires a valid owner, id, and handler.");
    }
    const existing = registrations.get(combo);
    if (existing) {
      options.onCollision?.({ combo, owner, existingOwner: existing.owner });
      throw new ShortcutCollisionError(combo, existing.owner);
    }
    const entry = Object.freeze({
      owner,
      id,
      combo,
      label: String(definition.label || id),
      handler: definition.handler,
      allowWhenTyping: definition.allowWhenTyping === true,
      core: definition.core === true,
    });
    registrations.set(combo, entry);
    let active = true;
    return () => {
      if (!active || registrations.get(combo) !== entry) return false;
      active = false;
      registrations.delete(combo);
      return true;
    };
  };

  const unregisterOwner = owner => {
    for (const [combo, entry] of registrations) {
      if (entry.owner === owner && !entry.core) registrations.delete(combo);
    }
  };

  const onKeydown = event => {
    if (event.defaultPrevented || event.isComposing || event.repeat) return;
    const entry = registrations.get(eventCombo(event));
    if (!entry || (isTypingTarget(event.target) && !entry.allowWhenTyping)) return;
    event.preventDefault();
    entry.handler(event);
  };

  const start = () => {
    if (started) return;
    started = true;
    target.addEventListener("keydown", onKeydown);
  };
  const stop = () => {
    if (!started) return;
    started = false;
    target.removeEventListener("keydown", onKeydown);
    registrations.clear();
  };

  const entries = () => Object.freeze([...registrations.values()].map(entry => Object.freeze({
    owner: entry.owner,
    id: entry.id,
    combo: entry.combo,
    label: entry.label,
    core: entry.core,
  })));

  return Object.freeze({ register, unregisterOwner, entries, start, stop });
}
