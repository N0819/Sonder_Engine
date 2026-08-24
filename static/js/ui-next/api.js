export const MODULE_RELEASE = "alpha98-ui7-516e7c3e67a7";

import {
  ApiError,
  apiErrorForStatus,
  malformedResponseError,
  normalizeApiError,
} from "./errors.js?release=alpha98-ui7-516e7c3e67a7";

const JSON_TYPES = (contentType) => (
  contentType.includes("application/json") || contentType.includes("+json")
);

function responseDetail(data) {
  if (typeof data === "string") return data;
  if (data && typeof data === "object") {
    return data.detail ?? data.message ?? data.error ?? data;
  }
  return "";
}

function correlationId(requestId) {
  const random = globalThis.crypto?.randomUUID?.()
    || Math.random().toString(36).slice(2, 12);
  return `ui-${requestId}-${random}`;
}

async function parseResponse(response, responseType, identity) {
  if (response.status === 204 || response.status === 205) return null;
  const text = await response.text();
  if (!text) return null;
  const contentType = response.headers.get("content-type") || "";
  if (responseType === "text") return text;
  if (responseType === "json" || JSON_TYPES(contentType)) {
    try {
      return JSON.parse(text);
    } catch {
      throw malformedResponseError({ ...identity, status: response.status });
    }
  }
  return text;
}

async function parseNdjsonResponse(response, identity, onEvent, collectEvents = true) {
  const events = collectEvents ? [] : null;
  const consumeLine = (line) => {
    if (!line.trim()) return;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      throw malformedResponseError({ ...identity, status: response.status });
    }
    if (events) events.push(event);
    onEvent?.(event);
  };

  if (!response.body?.getReader) {
    for (const line of (await response.text()).split(/\r?\n/)) consumeLine(line);
    return events;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  while (true) {
    const { done, value } = await reader.read();
    pending += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = pending.split(/\r?\n/);
    pending = lines.pop() || "";
    for (const line of lines) consumeLine(line);
    if (done) break;
  }
  consumeLine(pending);
  return events;
}

function ensureCurrent(active, channel, requestId, owner, isCurrent, identity) {
  if (active.get(channel)?.requestId !== requestId) {
    throw new ApiError("aborted", identity);
  }
  if (typeof isCurrent === "function" && !isCurrent({ owner, requestId })) {
    throw new ApiError("stale", identity);
  }
}

export function createApiClient(options = {}) {
  const fetchImpl = options.fetchImpl || globalThis.fetch.bind(globalThis);
  const active = new Map();
  let nextRequestId = 0;
  let sessionExpired = false;

  const cancelAll = (reason = "cancelled") => {
    for (const record of active.values()) record.controller.abort(reason);
    active.clear();
  };

  const cancel = (channel, reason = "cancelled") => {
    const record = active.get(String(channel));
    if (!record) return false;
    record.controller.abort(reason);
    active.delete(String(channel));
    return true;
  };

  const request = async (method, path, requestOptions = {}) => {
    const normalizedMethod = String(method || "GET").toUpperCase();
    const channel = String(requestOptions.channel || `${normalizedMethod}:${path}`);
    const owner = requestOptions.owner ?? null;
    const requestId = ++nextRequestId;
    const requestCorrelationId = correlationId(requestId);
    const identity = {
      requestId,
      correlationId: requestCorrelationId,
      status: 0,
    };

    if (sessionExpired) {
      throw new ApiError("session-expired", {
        ...identity,
        status: 401,
        technicalDetail: "The host session has expired.",
      });
    }

    active.get(channel)?.controller.abort("superseded");
    const controller = new AbortController();
    active.set(channel, { requestId, controller, owner });
    const headers = new Headers(requestOptions.headers || {});
    headers.set("Accept", requestOptions.responseType === "text"
      ? "text/plain, */*"
      : "application/json, application/x-ndjson, text/plain");
    headers.set("X-Sonder-Request-Id", requestCorrelationId);

    let body;
    if (requestOptions.body !== undefined) {
      if (requestOptions.body instanceof FormData
          || requestOptions.body instanceof URLSearchParams
          || typeof requestOptions.body === "string") {
        body = requestOptions.body;
      } else {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(requestOptions.body);
      }
    }

    options.onDiagnostic?.({
      phase: "start",
      method: normalizedMethod,
      path: String(path),
      channel,
      owner,
      requestId,
      correlationId: requestCorrelationId,
    });

    try {
      const response = await fetchImpl(new URL(path, options.baseUrl || location.origin), {
        method: normalizedMethod,
        headers,
        body,
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
      });
      ensureCurrent(
        active,
        channel,
        requestId,
        owner,
        requestOptions.isCurrent,
        identity,
      );
      if (response.ok) {
        requestOptions.onResponse?.({
          status: response.status,
          owner,
          requestId,
          correlationId: requestCorrelationId,
        });
      }
      const data = response.ok && requestOptions.parseResponse
        ? await requestOptions.parseResponse(response, identity)
        : await parseResponse(response, requestOptions.responseType, identity);
      ensureCurrent(
        active,
        channel,
        requestId,
        owner,
        requestOptions.isCurrent,
        identity,
      );

      if (!response.ok) {
        const error = apiErrorForStatus(response.status, {
          ...identity,
          technicalDetail: responseDetail(data),
          retryable: normalizedMethod === "GET" && response.status >= 500,
        });
        if (response.status === 401) {
          sessionExpired = true;
          cancelAll("session-expired");
          options.onSessionExpired?.({
            path: "/login",
            requestId,
            correlationId: requestCorrelationId,
          });
        }
        throw error;
      }

      options.onDiagnostic?.({
        phase: "complete",
        method: normalizedMethod,
        path: String(path),
        status: response.status,
        requestId,
        correlationId: requestCorrelationId,
      });
      return {
        data,
        status: response.status,
        owner,
        requestId,
        correlationId: requestCorrelationId,
      };
    } catch (error) {
      const normalized = normalizeApiError(error, {
        ...identity,
        aborted: controller.signal.aborted,
        method: normalizedMethod,
      });
      options.onDiagnostic?.({
        phase: "failed",
        method: normalizedMethod,
        path: String(path),
        kind: normalized.kind,
        status: normalized.status,
        requestId,
        correlationId: requestCorrelationId,
      });
      throw normalized;
    } finally {
      if (active.get(channel)?.requestId === requestId) active.delete(channel);
    }
  };

  const stream = async (path, streamOptions = {}) => {
    const result = await request(streamOptions.method || "GET", path, {
      ...streamOptions,
      parseResponse: (response, identity) => parseNdjsonResponse(
        response,
        identity,
        streamOptions.onEvent,
        streamOptions.collectEvents !== false,
      ),
    });
    return result;
  };

  return Object.freeze({
    request,
    get: (path, opts = {}) => request("GET", path, opts),
    post: (path, body, opts = {}) => request("POST", path, { ...opts, body }),
    put: (path, body, opts = {}) => request("PUT", path, { ...opts, body }),
    patch: (path, body, opts = {}) => request("PATCH", path, { ...opts, body }),
    delete: (path, opts = {}) => request("DELETE", path, opts),
    stream,
    cancel,
    cancelAll,
    isSessionExpired: () => sessionExpired,
  });
}
