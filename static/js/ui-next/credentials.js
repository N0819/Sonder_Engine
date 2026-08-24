export const MODULE_RELEASE = "alpha98-ui10-c14a4cf8dabd";

const SENSITIVE_KEY = /(password|passphrase|token|api.?key|secret|session|cookie|join.?code|authorization|^code$)/i;
const SENSITIVE_VALUE_PATTERNS = Object.freeze([
  [/\bBearer\s+[^\s,;]+/gi, "Bearer [redacted]"],
  [/\b(Basic)\s+[^\s,;]+/gi, "$1 [redacted]"],
  [/([?&](?:token|api_?key|secret|session|join_?code|code)=)[^&#\s]*/gi, "$1[redacted]"],
  [/\bsk-[A-Za-z0-9_-]{6,}/g, "[redacted]"],
]);

const APPROVED_ROUTES = Object.freeze([
  Object.freeze({
    method: "POST",
    pattern: /^\/api\/auth\/(?:setup|login)$/,
    fields: Object.freeze(["username", "password"]),
  }),
  Object.freeze({
    method: "POST",
    pattern: /^\/api\/join$/,
    fields: Object.freeze(["code"]),
  }),
  Object.freeze({
    method: "POST",
    pattern: /^\/api\/providers$/,
    fields: Object.freeze(["name", "kind", "base_url", "api_key"]),
  }),
  Object.freeze({
    method: "PUT",
    pattern: /^\/api\/providers\/[1-9][0-9]*$/,
    fields: Object.freeze(["name", "kind", "base_url", "api_key"]),
  }),
]);

export class CredentialError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "CredentialError";
    this.kind = kind;
  }
}

function redactString(value) {
  let output = String(value).slice(0, 2000);
  for (const [pattern, replacement] of SENSITIVE_VALUE_PATTERNS) {
    output = output.replace(pattern, replacement);
  }
  return output;
}

export function redactSensitive(value, seen = new WeakSet()) {
  if (typeof value === "string") return redactString(value);
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return "[circular]";
  seen.add(value);
  if (Array.isArray(value)) {
    return value.slice(0, 100).map(item => redactSensitive(item, seen));
  }
  const output = {};
  for (const [key, child] of Object.entries(value).slice(0, 100)) {
    output[key] = SENSITIVE_KEY.test(key)
      ? "[redacted]"
      : redactSensitive(child, seen);
  }
  return output;
}

export function containsSensitiveMaterial(value, seen = new WeakSet()) {
  if (typeof value === "string") return redactString(value) !== value;
  if (value === null || typeof value !== "object") return false;
  if (seen.has(value)) return false;
  seen.add(value);
  for (const [key, child] of Object.entries(value)) {
    if (SENSITIVE_KEY.test(key) || containsSensitiveMaterial(child, seen)) return true;
  }
  return false;
}

export function assertSafeToPersist(value) {
  if (containsSensitiveMaterial(value)) {
    throw new CredentialError(
      "sensitive-material",
      "Credential material cannot enter browser-local state.",
    );
  }
  return value;
}

function matchingRoute(method, endpoint) {
  return APPROVED_ROUTES.find(route => (
    route.method === method && route.pattern.test(endpoint)
  ));
}

function clearSensitiveControls(form) {
  if (!form?.elements) return;
  for (const control of form.elements) {
    if (!("value" in control)) continue;
    if (control.type === "password" || SENSITIVE_KEY.test(control.name || "")) {
      control.value = "";
    }
  }
}

export async function submitCredentialForm({
  form,
  apiClient,
  method = "POST",
  endpoint,
}) {
  try {
    if (!form?.elements || typeof apiClient?.request !== "function") {
      throw new CredentialError("credential-form", "A form and API client are required.");
    }
    const normalizedMethod = String(method).toUpperCase();
    const normalizedEndpoint = String(endpoint || "");
    const route = matchingRoute(normalizedMethod, normalizedEndpoint);
    if (!route) {
      throw new CredentialError("credential-route", "That credential route is not approved.");
    }
    const allowed = new Set(route.fields);
    const body = {};
    for (const control of form.elements) {
      const name = String(control.name || "");
      if (!name || control.disabled || !("value" in control)) continue;
      if (!allowed.has(name)) {
        throw new CredentialError("credential-field", `Credential field is not approved: ${name}`);
      }
      body[name] = String(control.value);
    }
    return await apiClient.request(normalizedMethod, normalizedEndpoint, {
      body,
      channel: `credential:${normalizedEndpoint}`,
      owner: "credential-form",
    });
  } finally {
    clearSensitiveControls(form);
  }
}
