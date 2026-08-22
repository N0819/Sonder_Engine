export const MODULE_RELEASE = "wp02.1";

const SENSITIVE_KEY = /(password|passphrase|token|api.?key|secret|session|cookie|join.?code|authorization)/i;
const SENSITIVE_VALUE_PATTERNS = Object.freeze([
  [/\bBearer\s+[^\s,;]+/gi, "Bearer [redacted]"],
  [/\b(Basic)\s+[^\s,;]+/gi, "$1 [redacted]"],
  [/([?&](?:token|api_?key|secret|session|join_?code)=)[^&#\s]*/gi, "$1[redacted]"],
  [/\bsk-[A-Za-z0-9_-]{6,}/g, "[redacted]"],
]);

function redactString(value) {
  let output = String(value).slice(0, 2000);
  for (const [pattern, replacement] of SENSITIVE_VALUE_PATTERNS) {
    output = output.replace(pattern, replacement);
  }
  return output;
}

function redact(value, seen = new WeakSet()) {
  if (typeof value === "string") return redactString(value);
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return "[circular]";
  seen.add(value);
  if (Array.isArray(value)) return value.slice(0, 100).map(item => redact(item, seen));
  const output = {};
  for (const [key, child] of Object.entries(value).slice(0, 100)) {
    output[key] = SENSITIVE_KEY.test(key) ? "[redacted]" : redact(child, seen);
  }
  return output;
}

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
    entries.push(deepFreeze(redact(entry)));
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
