export const MODULE_RELEASE = "alpha98-ui11-0acc47fb0573";

// UI_CATALOG_START: player-safe error copy.
const PLAYER_MESSAGES = Object.freeze({
  network: "Sonder could not reach the engine. Your work is still here.",
  "session-expired": "Your Sonder session ended. Sign in to continue.",
  forbidden: "This account cannot perform that action.",
  validation: "Some information needs your attention.",
  "not-found": "That item is no longer available.",
  conflict: "This changed somewhere else. Review both versions before saving.",
  server: "Sonder could not complete that action.",
  "malformed-response": "Sonder received an unreadable response.",
  aborted: "The earlier request was replaced.",
  stale: "The result belongs to an older selection.",
});
// UI_CATALOG_END

const STATUS_KINDS = Object.freeze({
  400: "validation",
  401: "session-expired",
  403: "forbidden",
  404: "not-found",
  409: "conflict",
  422: "validation",
});

function boundedDetail(value, limit = 500) {
  if (value === undefined || value === null) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return String(text).replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, limit);
}

export class ApiError extends Error {
  constructor(kind, options = {}) {
    const normalizedKind = PLAYER_MESSAGES[kind] ? kind : "server";
    super(PLAYER_MESSAGES[normalizedKind]);
    this.name = "ApiError";
    this.kind = normalizedKind;
    this.status = Number(options.status || 0);
    this.userMessage = PLAYER_MESSAGES[normalizedKind];
    this.technicalDetail = boundedDetail(options.technicalDetail);
    this.requestId = Number(options.requestId || 0);
    this.correlationId = String(options.correlationId || "");
    this.retryable = Boolean(options.retryable);
  }
}

export function apiErrorForStatus(status, options = {}) {
  const numericStatus = Number(status || 0);
  const kind = STATUS_KINDS[numericStatus]
    || (numericStatus >= 500 ? "server" : "server");
  return new ApiError(kind, { ...options, status: numericStatus });
}

export function normalizeApiError(error, options = {}) {
  if (error instanceof ApiError) return error;
  if (error?.name === "AbortError" || options.aborted) {
    return new ApiError("aborted", options);
  }
  return new ApiError("network", {
    ...options,
    technicalDetail: error?.message || "Network request failed.",
    retryable: String(options.method || "GET").toUpperCase() === "GET",
  });
}

export function malformedResponseError(options = {}) {
  return new ApiError("malformed-response", {
    ...options,
    technicalDetail: "Response was not valid JSON.",
  });
}
