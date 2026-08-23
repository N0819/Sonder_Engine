export const MODULE_RELEASE = "alpha98-ui2-3f44d1cc71ed";

import { redactSensitive } from "./credentials.js?release=alpha98-ui2-3f44d1cc71ed";

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

export function createDiagnostics(options = {}) {
  const limit = Math.max(1, Math.min(500, Number(options.limit || 100)));
  let enabled = options.enabled === true;
  const entries = [];

  const record = (entry) => {
    if (!enabled) return false;
    entries.push(deepFreeze(redactSensitive(entry)));
    if (entries.length > limit) entries.splice(0, entries.length - limit);
    options.onChange?.(entries.length);
    return true;
  };

  const setEnabled = (value) => {
    enabled = value === true;
    return enabled;
  };

  const clear = () => {
    entries.length = 0;
    options.onChange?.(0);
  };

  return Object.freeze({
    record,
    setEnabled,
    isEnabled: () => enabled,
    snapshot: () => Object.freeze([...entries]),
    clear,
  });
}
